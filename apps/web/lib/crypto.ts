import "server-only";
import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";

/**
 * AES-256-GCM, shared with the Python worker.
 * Format: "v1:" + base64( iv[12] || ciphertext || tag[16] )
 */
function key(): Buffer {
  const raw = process.env.MASTER_KEY ?? "";
  const buf = Buffer.from(raw, "base64");
  if (buf.length !== 32) throw new Error("MASTER_KEY must be base64 of exactly 32 bytes");
  return buf;
}

export function hasMasterKey(): boolean {
  try {
    key();
    return true;
  } catch {
    return false;
  }
}

export function encrypt(plain: string): string {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key(), iv, { authTagLength: 16 });
  const ct = Buffer.concat([cipher.update(plain, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return "v1:" + Buffer.concat([iv, ct, tag]).toString("base64");
}

export function decrypt(payload: string): string {
  if (!payload.startsWith("v1:")) throw new Error("Unknown ciphertext version");
  const buf = Buffer.from(payload.slice(3), "base64");
  if (buf.length < 12 + 16) throw new Error("Ciphertext is too short");
  const iv = buf.subarray(0, 12);
  const tag = buf.subarray(buf.length - 16);
  const ct = buf.subarray(12, buf.length - 16);
  // Pin the tag length: Node otherwise accepts truncated (4–15 byte) tags.
  const decipher = createDecipheriv("aes-256-gcm", key(), iv, { authTagLength: 16 });
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(ct), decipher.final()]).toString("utf8");
}
