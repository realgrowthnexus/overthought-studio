import { ButtonLink } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh items-center justify-center p-6">
      <EmptyState title="Nothing here" action={<ButtonLink href="/" variant="primary">Go to overview</ButtonLink>}>
        This page doesn&apos;t exist, or it was removed.
      </EmptyState>
    </main>
  );
}
