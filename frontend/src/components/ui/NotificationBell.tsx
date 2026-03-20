import { useState, useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AlertsService, { Notification } from "../../services/alerts.service";

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const { data: countData } = useQuery({
    queryKey: ["unread-count"],
    queryFn: AlertsService.getUnreadCount,
    refetchInterval: 30_000,
  });

  const { data: notifData } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => AlertsService.listNotifications({ page: 1 }),
    enabled: open,
  });

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleMarkAll = async () => {
    await AlertsService.markAllRead();
    queryClient.invalidateQueries({ queryKey: ["unread-count"] });
    queryClient.invalidateQueries({ queryKey: ["notifications"] });
  };

  const handleMarkOne = async (id: number) => {
    await AlertsService.markRead(id);
    queryClient.invalidateQueries({ queryKey: ["unread-count"] });
    queryClient.invalidateQueries({ queryKey: ["notifications"] });
  };

  const count = countData ?? 0;

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        className="notif-bell"
        onClick={() => setOpen(o => !o)}
        title="Notifications"
      >
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path d="M9 2a5 5 0 00-5 5v3l-1.5 2h13L14 10V7a5 5 0 00-5-5z" stroke="currentColor" strokeWidth="1.3"/>
          <path d="M7 14a2 2 0 004 0" stroke="currentColor" strokeWidth="1.3"/>
        </svg>
        {count > 0 && (
          <span className="notif-badge">{count > 99 ? "99+" : count}</span>
        )}
      </button>

      {open && (
        <div className="notif-dropdown">
          <div className="notif-header">
            <span>Notifications</span>
            {count > 0 && (
              <button className="notif-mark-all" onClick={handleMarkAll}>
                Mark all read
              </button>
            )}
          </div>

          <div className="notif-list">
            {!notifData?.notifications.length ? (
              <div className="notif-empty">No notifications yet</div>
            ) : (
              notifData.notifications.map((n: Notification) => (
                <div
                  key={n.id}
                  className={`notif-item ${n.status === "unread" ? "unread" : ""}`}
                  onClick={() => n.status === "unread" && handleMarkOne(n.id)}
                >
                  {n.status === "unread" && <span className="notif-dot" />}
                  <div className="notif-content">
                    <div className="notif-title">{n.title}</div>
                    <div className="notif-msg">{n.message}</div>
                    <div className="notif-time">
                      {new Date(n.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
