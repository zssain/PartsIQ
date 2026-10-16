import type { JSX } from "react";

import { Chat } from "@/components/chat/Chat";

// Dynamic chat route. In Next 16 route params are async.
export default async function ChatPage({ params }: { params: Promise<{ id: string }> }): Promise<JSX.Element> {
  const { id } = await params;
  return (
    <main>
      <h1>Your enquiry</h1>
      <Chat enquiryId={id} />
    </main>
  );
}
