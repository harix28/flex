# Accessibility and Usability Checklist

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

- Keyboard navigation covers filters, charts, dialogs, work-order transitions and chapter-like tutorials.
- Visible focus; labeled native controls; errors associated with fields; dynamic results announced without reading every sensor frame.
- Red/amber/green/gray have text equivalents. Unknown is not represented only by gray.
- Chart axes specify sensor units and cycle/time semantics; missing segments remain visible. Provide a table or textual summary for critical evidence.
- Layout reflows for mobile; minimum readable text, adequate contrast, large task controls. Verify with actual screenshots and keyboard tests.
- Respect reduced-motion; animation never conveys exclusive operational information.
- Approval dialogs identify asset/action/version and retain focus. No accidental action from scanning a QR alone.
- Hinglish/Hindi UI copy can be localized, while internal status codes remain stable. Time display includes timezone; storage remains UTC.
