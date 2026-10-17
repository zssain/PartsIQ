import { BrandLogo } from "@/components/BrandLogo";
export function SiteFooter() {
 return <footer className="pq-site-footer"><div className="pq-container"><div className="pq-footer-top"><div><BrandLogo /><p>Clarity in every connection.</p></div><nav aria-label="Footer"><a href="/demo">Explore workspace ↗</a><a href="/architecture">System design ↗</a><a href="/staff/inbox">Staff inbox ↗</a><a href="/login">Staff sign in ↗</a></nav></div><div className="pq-footer-bottom"><span>© PartsIQ · Independent synthetic demonstration.<br />Fabricated data. Not affiliated with any distributor.</span><span>DESIGNED AROUND HUMAN JUDGEMENT.</span></div></div></footer>;
}
