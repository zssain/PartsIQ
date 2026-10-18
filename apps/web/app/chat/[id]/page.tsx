import type { JSX } from "react";

import { Chat } from "@/components/chat/Chat";
import { CustomerProgress } from "@/components/visibility/CustomerProgress";
import { FixtureBanner } from "@/components/visibility/FixtureBanner";

// Dynamic chat route. In Next 16 route params are async. The persisted-timeline progress panel is
// mounted above the chat so the customer sees each real pipeline step as it happens; the fixture
// banner labels the synthetic mode honestly.
export default async function ChatPage({ params }: { params: Promise<{ id: string }> }): Promise<JSX.Element> {
  const { id } = await params;
  return (
    <main>
      <h1>Your enquiry</h1>
      <FixtureBanner />
      <CustomerProgress enquiryId={id} />
      <Chat enquiryId={id} />
    </main>
  );
}
