import type { JSX } from "react";

import { Workspace } from "@/components/review/Workspace";

export default async function StaffEnquiryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<JSX.Element> {
  const { id } = await params;
  return (
    <main>
      <h1>Review enquiry</h1>
      <Workspace enquiryId={id} />
    </main>
  );
}
