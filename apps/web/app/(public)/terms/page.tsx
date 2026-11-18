import type { Metadata } from "next";
import { appDomain } from "@/lib/env";

export const metadata: Metadata = { title: "Terms of service", robots: { index: true, follow: true } };

const UPDATED = "November 18, 2026";

export default function TermsPage() {
  const domain = appDomain();
  const contact = `support@${domain}`;
  return (
    <article className="prose-studio">
      <h1>Terms of service</h1>
      <p><em>Last updated {UPDATED}</em></p>
      <p>
        These terms cover use of Overthought Studio (“the app”), a private tool operated by the owner of {domain} to produce and publish
        educational videos to TikTok accounts the owner controls.
      </p>

      <h2>Who can use it</h2>
      <p>Only the owner and people the owner authorizes. Sign-up is closed. You must be at least 18 and allowed to manage each TikTok account you connect.</p>

      <h2>Connecting TikTok</h2>
      <p>
        Accounts connect through TikTok’s official Login Kit and Content Posting API. By connecting an account you authorize the app to read the
        profile and video information described in our <a href="/privacy">privacy policy</a> and to upload or publish videos you’ve approved.
        You can revoke access at any time in TikTok’s settings.
      </p>

      <h2>Content</h2>
      <ul>
        <li>The account owner is responsible for every video published and for following TikTok’s Community Guidelines and Terms of Service.</li>
        <li>Videos are labelled as AI-generated content where TikTok’s rules require it.</li>
        <li>The app doesn’t automate likes, follows, comments or messages, and doesn’t post to accounts the owner doesn’t control.</li>
      </ul>

      <h2>Availability</h2>
      <p>The app is provided as is. We may change or stop it at any time. We aren’t liable for missed posts, lost data or decisions TikTok makes about an account.</p>

      <h2>Ending use</h2>
      <p>Disconnecting an account deletes its tokens. To delete all stored data about an account, email <a href={`mailto:${contact}`}>{contact}</a>.</p>

      <h2>Changes</h2>
      <p>We may update these terms and will change the date above when we do.</p>

      <h2>Contact</h2>
      <p><a href={`mailto:${contact}`}>{contact}</a></p>
    </article>
  );
}
