'use client';

import { useEffect, useState } from 'react';
import { listNotifications, subscribeToNotifications, patchNotification } from '@/lib/api';
import type { Notification } from '@/types/notification';
import NotificationCard from '@/components/notification-card';
import NotificationCardSkeleton from '@/components/notification-card-skeleton';

export default function DashboardPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchNotifications = async () => {
      try {
        setLoading(true);
        const data = await listNotifications();
        setNotifications(data);
      } catch (error) {
        console.error('Failed to fetch notifications:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchNotifications();

    // Subscribe to SSE updates
    const unsubscribe = subscribeToNotifications((newNotification: Notification) => {
      setNotifications((prev) => [newNotification, ...prev]);
    });

    return () => {
      unsubscribe();
    };
  }, []);

  const groupedByUrgency = {
    Critical: notifications.filter((n) => n.urgency === 'critical'),
    High: notifications.filter((n) => n.urgency === 'high'),
    Medium: notifications.filter((n) => n.urgency === 'medium'),
    Low: notifications.filter((n) => n.urgency === 'low'),
  };

  const handleDismiss = async (id: string) => {
    try {
      await patchNotification(id, { state: 'dismissed' });
      setNotifications((prev) => prev.filter((n) => n.id !== id));
    } catch (error) {
      console.error('Failed to dismiss notification:', error);
    }
  };

  if (loading) {
    return (
      <div className="p-6 max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">Notifications</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <NotificationCardSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  const hasNotifications = Object.values(groupedByUrgency).some((group) => group.length > 0);

  if (!hasNotifications) {
    return (
      <div className="p-6 max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">Notifications</h1>
        <div className="flex flex-col items-center justify-center py-12">
          <svg
            className="w-16 h-16 text-gray-400 mb-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
            />
          </svg>
          <p className="text-xl font-semibold text-gray-700 mb-2">All caught up!</p>
          <p className="text-gray-500">You have no notifications at the moment.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">Notifications</h1>

      {(
        ['Critical', 'High', 'Medium', 'Low'] as const
      ).map((urgencyLevel) => {
        const group = groupedByUrgency[urgencyLevel];
        if (group.length === 0) return null;

        return (
          <div key={urgencyLevel} className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">{urgencyLevel}</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {group.map((notification) => (
                <NotificationCard
                  key={notification.id}
                  notification={notification}
                  onDismiss={handleDismiss}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
