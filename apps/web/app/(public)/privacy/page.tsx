import type { Metadata } from "next";
import { appDomain } from "@/lib/env";

export const metadata: Metadata = { title: "Privacy policy", robots: { index: true, follow: true } };

const UPDATED = "November 18, 2026";

export default function PrivacyPage() {
  const domain = appDomain();
  const contact = `privacy@${domain}`;
  return (
    <article className="prose-studio">
      <h1>Privacy policy</h1>
      <p><em>Last updated {UPDATED}</em></p>
      <p>
        Overthought Studio (“the app”, “we”) is a private publishing tool operated by the owner of {domain}. It produces short
        educational videos and publishes them to TikTok accounts that the owner controls. The app is not offered to the public, and
        only the owner can sign in.
      </p>

      <h2>What we access from TikTok</h2>
      <p>When the owner connects a TikTok account through TikTok Login Kit, TikTok asks for consent and then shares only what the granted scopes allow:</p>
      <ul>
        <li><strong>user.info.basic, user.info.profile:</strong> account ID (open_id), display name, username, avatar and verification status, so we can show which account is connected.</li>
        <li><strong>user.info.stats:</strong> follower, following, like and video counts, to track channel growth.</li>
        <li><strong>video.list:</strong> the account’s public videos and their view, like, comment and share counts, to measure how each video performs.</li>
        <li><strong>video.upload, video.publish:</strong> to send videos the owner has approved to the account’s drafts or post them, and to check their publishing status. We also read the account’s posting options (such as allowed privacy levels) before each post.</li>
      </ul>
      <p>We don’t access direct messages, contacts, other users’ personal data or anything outside these scopes.</p>

      <h2>How we use it</h2>
      <p>
        Only to operate the owner’s own channels: publishing videos, showing performance on the owner’s dashboard, and deciding which topics
        to make next. We don’t sell, rent or share TikTok data with anyone, and we don’t use it for advertising.
      </p>

      <h2>How we store it</h2>
      <ul>
        <li>Access and refresh tokens are encrypted with AES-256-GCM before they’re stored, and are only decrypted on our servers when calling TikTok’s API.</li>
        <li>Data is held in a managed Postgres database (Supabase, United States) protected by row-level security. Only the owner’s account can read it.</li>
        <li>All traffic uses HTTPS.</li>
      </ul>

      <h2>How long we keep it</h2>
      <p>
        Account data and statistics are kept while the account stays connected. Video files are deleted from our storage a few weeks after
        they’re published. When the owner disconnects an account, its tokens are deleted immediately.
      </p>

      <h2>Deleting your data</h2>
      <p>
        You can revoke the app’s access at any time in the TikTok app under Settings and privacy → Security → Manage app permissions. To have all
        stored data about an account deleted, email <a href={`mailto:${contact}`}>{contact}</a>; we delete it within 30 days.
      </p>

      <h2>Other services we use</h2>
      <p>
        To make videos we use AI services for writing (Anthropic) and images (RunPod); the voiceover is generated on our own server. These services receive the video
        topic and script only, never TikTok account data.
      </p>

      <h2>Children</h2>
      <p>The app is not directed at children and is used only by its adult owner.</p>

      <h2>Changes</h2>
      <p>If this policy changes, we update the date at the top of this page.</p>

      <h2>Contact</h2>
      <p>Questions: <a href={`mailto:${contact}`}>{contact}</a>.</p>
    </article>
  );
}
