"use server";
import { z } from "zod";
import { requireAdmin } from "@/lib/auth";
import { serviceClient } from "@/lib/supabase/service";
import {
  approveVideo, cancelJob, enqueueJob, rejectVideo, retryJob, scheduleVideo, setChannelStatus, setGlobalPause,
  type ActionResult,
} from "@/lib/actions";

export type AssistantAction = {
  type: string; label: string; channel_id?: string; video_id?: string; job_id?: number; when?: string;
  done?: boolean; result?: string;
};
export type AssistantMessage = {
  id: number; role: "user" | "assistant"; content: string; actions: AssistantAction[];
  status: "pending" | "done" | "error"; created_at: string;
};
export type AssistantState = { messages: AssistantMessage[]; signedIn: boolean; limitedUntil: string | null };

const PENDING_STALE_MS = 10 * 60_000;     // a reply the worker never picked up stops blocking the input

async function guard<T>(fn: () => Promise<ActionResult<T>>): Promise<ActionResult<T>> {
  try {
    await requireAdmin();
    return await fn();
  } catch (e) {
    if (e instanceof z.ZodError) return { ok: false, error: e.issues.map((i) => i.message).join("; ") };
    return { ok: false, error: e instanceof Error ? e.message : "Something went wrong." };
  }
}

export async function loadAssistant(): Promise<ActionResult<AssistantState>> {
  return guard(async () => {
    const db = serviceClient();
    const [{ data: rows, error }, { data: svc }] = await Promise.all([
      db.from("assistant_messages").select("id,role,content,actions,status,created_at").order("id", { ascending: false }).limit(60),
      db.from("services").select("status,details").eq("name", "anthropic").maybeSingle(),
    ]);
    if (error) throw new Error(error.message);
    const now = Date.now();
    const messages = ((rows ?? []) as AssistantMessage[]).reverse().map((m) =>
      m.status === "pending" && now - new Date(m.created_at).getTime() > PENDING_STALE_MS
        ? { ...m, status: "error" as const, content: "The worker didn't answer this one. Is the worker online? Try again." }
        : m,
    );
    const d = (svc?.details ?? {}) as Record<string, unknown>;
    const resume = typeof d.resume_at === "string" ? d.resume_at : null;
    const limitedUntil = d.limited === true && resume && new Date(resume).getTime() > now ? resume : null;
    return { ok: true, data: { messages, signedIn: Boolean(svc) && svc?.status !== "unconfigured", limitedUntil } };
  });
}

export async function askAssistant(text: string): Promise<ActionResult> {
  return guard(async () => {
    const content = z.string().trim().min(1, "Type a question first.").max(2000, "Keep it under 2000 characters.").parse(text);
    const db = serviceClient();
    const since = new Date(Date.now() - PENDING_STALE_MS).toISOString();
    const { data: waiting } = await db.from("assistant_messages").select("id").eq("status", "pending").gte("created_at", since).limit(1);
    if (waiting?.length) return { ok: false, error: "Still answering your last question." };
    const { error: e1 } = await db.from("assistant_messages").insert({ role: "user", content, status: "done" });
    if (e1) throw new Error(e1.message);
    const { data: reply, error: e2 } = await db.from("assistant_messages")
      .insert({ role: "assistant", content: "", status: "pending" }).select("id").single();
    if (e2 || !reply) throw new Error(e2?.message ?? "Could not save the question.");
    const { error: e3 } = await db.from("jobs").insert({
      type: "assistant_reply", payload: { reply_id: reply.id }, priority: 1, dedupe_key: `assistant_reply:${reply.id}`,
    });
    if (e3) {
      await db.from("assistant_messages").update({ status: "error", content: "Couldn't reach the worker. Try again." }).eq("id", reply.id);
      throw new Error(e3.message);
    }
    return { ok: true };
  });
}

/** Runs one proposed button. The action is read from the saved message (never from the browser), then handed to the
 *  normal admin-checked dashboard action, which validates it again. */
export async function runAssistantAction(messageId: number, index: number): Promise<ActionResult> {
  return guard(async () => {
    const id = z.number().int().positive().parse(messageId);
    const i = z.number().int().min(0).max(9).parse(index);
    const db = serviceClient();
    const { data: msg } = await db.from("assistant_messages").select("id,role,actions").eq("id", id).maybeSingle();
    const actions = (msg?.actions ?? []) as AssistantAction[];
    const a = actions[i];
    if (!msg || msg.role !== "assistant" || !a) return { ok: false, error: "That button isn't available any more." };
    if (a.done) return { ok: false, error: "Already done." };
    let r: ActionResult;
    switch (a.type) {
      case "pause_channel": r = await setChannelStatus(a.channel_id ?? "", "paused"); break;
      case "resume_channel": r = await setChannelStatus(a.channel_id ?? "", "active"); break;
      case "pause_studio": r = await setGlobalPause(true); break;
      case "resume_studio": r = await setGlobalPause(false); break;
      case "make_video": r = await enqueueJob({ type: "plan_channel", payload: { channel_id: a.channel_id, force: true } }); break;
      case "retry_job": r = await retryJob(Number(a.job_id)); break;
      case "cancel_job": r = await cancelJob(Number(a.job_id)); break;
      case "approve_video": r = await approveVideo(a.video_id ?? ""); break;
      case "reject_video": r = await rejectVideo(a.video_id ?? "", ""); break;
      case "publish_now": r = await enqueueJob({ type: "publish_video", payload: { video_id: a.video_id } }); break;
      case "schedule_video": r = await scheduleVideo(a.video_id ?? "", a.when ?? null); break;
      case "clear_schedule": r = await scheduleVideo(a.video_id ?? "", null); break;
      default: return { ok: false, error: "The studio doesn't know that action." };
    }
    const result = r.ok ? (r.message ?? "Done.") : r.error;
    if (r.ok) {
      actions[i] = { ...a, done: true, result };
      await db.from("assistant_messages").update({ actions }).eq("id", id);
    }
    await db.from("assistant_messages").insert({ role: "assistant", content: `${r.ok ? "Done" : "Didn't work"}: ${a.label}. ${result}`, status: "done" });
    await db.from("events").insert({ scope: "assistant", level: r.ok ? "info" : "warn", message: `Assistant button "${a.label}": ${result}` });
    return r;
  });
}
