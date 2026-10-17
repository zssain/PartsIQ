// F35 Stock freshness — typed client surface (owner search; called internally by staff review).
//
// The browser never re-reads stock itself; it displays the server's freshness verdict. This
// lib exposes the typed result shape so the staff review page can render it. It submits only
// typed identifiers, never browser-authored stock or compatibility facts.

export interface F35Result {
  fresh: boolean;
  changed_item_ids: string[];
  checked_at: string;
}

export interface F35Request {
  // The staff page carries the enquiry/revision it is reviewing; the gateway attaches the
  // verified facts and freshness window server-side before calling the search check.
  enquiry_id: string;
  expected_revision: number;
}
