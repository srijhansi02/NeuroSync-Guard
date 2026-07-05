import React, { useEffect, useMemo, useRef } from "react";
import landingPageHtml from "../neurosync-guard-landing.html?raw";

export default function LandingPage({ onGetStarted }) {
  const iframeRef = useRef(null);

  useEffect(() => {
    const handleMessage = (event) => {
      if (event.data?.type === "neurosync-get-started") {
        onGetStarted?.();
      }
    };

    const handleFrameClick = (event) => {
      const target = event.target;
      const trigger = target instanceof Element
        ? target.closest(".nav-cta, .hero-ctas .btn-primary, .final-cta .btn-primary")
        : null;

      if (trigger) {
        event.preventDefault();
        event.stopPropagation();
        onGetStarted?.();
      }
    };

    const iframe = iframeRef.current;
    window.addEventListener("message", handleMessage);

    if (iframe?.contentWindow) {
      iframe.contentWindow.addEventListener("click", handleFrameClick);
    }

    return () => {
      window.removeEventListener("message", handleMessage);
      if (iframe?.contentWindow) {
        iframe.contentWindow.removeEventListener("click", handleFrameClick);
      }
    };
  }, [onGetStarted]);

  const pageHtml = useMemo(() => {
    const withScrollOffset = landingPageHtml.replace(
      "</style>",
      "\n  section{scroll-margin-top:96px;}\n</style>"
    );

    return withScrollOffset.replace(
      "</body>",
      `
<script>
  document.addEventListener("DOMContentLoaded", () => {
    const triggers = document.querySelectorAll(".nav-cta, .hero-ctas .btn-primary, .final-cta .btn-primary");
    triggers.forEach((trigger) => {
      trigger.addEventListener("click", (event) => {
        event.preventDefault();
        if (window.parent && window.parent !== window) {
          window.parent.postMessage({ type: "neurosync-get-started" }, "*");
        } else {
          window.location.hash = "#cta";
        }
      });
    });
  });
</script>
</body>`
    );
  }, []);

  return (
    <div style={{ width: "100vw", height: "100vh", overflow: "hidden", background: "#05060b" }}>
      <iframe
        ref={iframeRef}
        title="NeuroSync Guard landing page"
        srcDoc={pageHtml}
        style={{ width: "100%", height: "100%", border: "none", display: "block", background: "#05060b" }}
      />
    </div>
  );
}
