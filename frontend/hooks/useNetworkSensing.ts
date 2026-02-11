import { useEffect, useState } from "react";

export function useNetworkSensing() {
  const [quality, setQuality] = useState<"slow" | "fast">("fast");

  useEffect(() => {
    const updateQuality = () => {
      const conn =
        (navigator as any).connection ||
        (navigator as any).mozConnection ||
        (navigator as any).webkitConnection;
      if (conn) {
        if (
          conn.downlink < 1.5 ||
          ["3g", "2g", "slow-2g"].includes(conn.effectiveType)
        ) {
          setQuality("slow");
        } else {
          setQuality("fast");
        }
      }
    };

    updateQuality();
    const nav = navigator as any;
    nav.connection?.addEventListener("change", updateQuality);
    return () => nav.connection?.removeEventListener("change", updateQuality);
  }, []);

  return quality;
}
