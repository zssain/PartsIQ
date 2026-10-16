# PartsIQ brand system

Use supplied falcon/gear/magnifier bilingual mark. Preserve aspect ratio;do not redraw the Arabic text. Primary navy#2B2D7F and gold#C59A45 are standardized tokens;the raster artwork also contains gradients and antialiasing. Gold is decorative/accent,not small text on white. Use navy for primary action,neutral surfaces and semantic state colours from tokens.json. Dark-mode muted/border overrides preserve readable contrast.

Typography: Noto Sans for English,Noto Sans Arabic for Arabic UI,Noto Naskh Arabic for Arabic PDF. Licensed font files and OFL notices are bundled. Use font-display:swap;self-host fonts;never depend on external PDF font fetch. Use bdi for part numbers and serials.

Use full lockup at minimum160CSSpx width in header/landing;icon-only at24/32px when space is constrained. Leave clear space equal to one-quarter icon width. Never stretch,crop critical mark elements,place on a busy photo or imply endorsement by a dealer. Small favicon uses supplied icon crop,not illegible full bilingual lockup.

Exports: favicon ICO16/32/48;PNG16/32/48/96;Apple180;PWA192/512;maskable192/512;social1200x630;profile1080;full logo320/640/1280. Existing supplied pack is preserved under assets. Asset manifest records actual dimensions and SHA256;use it rather than guessing file names. No authentic vector source was supplied,so no SVG is falsely presented as original artwork.

Prompt18 copies every manifest-listed asset and fonts into apps/web/public/brand. PDF worker copies the same font bytes and logo into its image. Brand exports are already bundled;new raster editing is unnecessary.
