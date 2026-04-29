'use client';

import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

interface FocusSession {
  id: string;
  started_at: string;
  planned_minutes: number;
}

interface FocusSessionResponse {
  session: FocusSession;
}

interface FocusEndResponse {
  success: boolean;
  session_id: string;
}

interface FocusHistoryResponse {
  session: FocusSession | null;
}

export default function DeepWorkPage() {
  const [session, setSession] = useState<FocusSession | null>(null);
  const [plannedMinutes, setPlannedMinutes] = useState(50);
  const [timeRemaining, setTimeRemaining] = useState(0);
  const [showFeedbackDialog, setShowFeedbackDialog] = useState(false);
  const [rating, setRating] = useState<number | null>(null);
  const [notes, setNotes] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isFeedbackLoading, setIsFeedbackLoading] = useState(false);

  // Get current focus session on mount
  useEffect(() => {
    const getCurrentFocus = async () => {
      try {
        const response = await fetch('/api/focus/current', {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
        });
        if (response.ok) {
          const data: FocusHistoryResponse = await response.json();
          if (data.session) {
            setSession(data.session);
            setPlannedMinutes(data.session.planned_minutes);
          }
        }
      } catch (error) {
        console.error('Error fetching current focus session:', error);
      } finally {
        setIsLoading(false);
      }
    };

    getCurrentFocus();
  }, []);

  // Countdown timer logic
  useEffect(() => {
    if (!session) return;

    const interval = setInterval(() => {
      const startedAt = new Date(session.started_at).getTime();
      const now = Date.now();
      const elapsedMs = now - startedAt;
      const totalMs = session.planned_minutes * 60 * 1000;
      const remaining = Math.max(0, totalMs - elapsedMs);

      setTimeRemaining(remaining);

      if (remaining === 0) {
        clearInterval(interval);
      }
    }, 100);

    return () => clearInterval(interval);
  }, [session]);

  const formatTime = (ms: number) => {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  };

  const startFocus = async () => {
    try {
      const response = await fetch('/api/focus/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ planned_minutes: plannedMinutes }),
      });
      if (response.ok) {
        const data: FocusSessionResponse = await response.json();
        setSession(data.session);
      }
    } catch (error) {
      console.error('Error starting focus session:', error);
    }
  };

  const endFocus = async () => {
    if (!session) return;
    try {
      const response = await fetch('/api/focus/end', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: session.id }),
      });
      if (response.ok) {
        setShowFeedbackDialog(true);
      }
    } catch (error) {
      console.error('Error ending focus session:', error);
    }
  };

  const submitFeedback = async () => {
    if (!session || rating === null) return;
    setIsFeedbackLoading(true);
    try {
      const response = await fetch('/api/focus/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: session.id,
          rating,
          notes: notes || undefined,
        }),
      });
      if (response.ok) {
        setSession(null);
        setShowFeedbackDialog(false);
        setRating(null);
        setNotes('');
      }
    } catch (error) {
      console.error('Error submitting feedback:', error);
    } finally {
      setIsFeedbackLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 p-8">
      <div className="max-w-2xl mx-auto">
        <Card className="bg-slate-800 border-slate-700 text-white">
          <CardHeader>
            <CardTitle className="text-3xl">Deep Work Session</CardTitle>
            <CardDescription className="text-slate-400">
              Focus on one task at a time
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {!session ? (
              <div className="space-y-4">
                <div>
                  <label htmlFor="planned-minutes" className="block text-sm font-medium mb-2">
                    Planned Minutes
                  </label>
                  <Input
                    id="planned-minutes"
                    type="number"
                    min="1"
                    max="480"
                    value={plannedMinutes}
                    onChange={(e) => setPlannedMinutes(Math.max(1, parseInt(e.target.value) || 1))}
                    className="bg-slate-700 border-slate-600 text-white"
                  />
                </div>
                <Button
                  onClick={startFocus}
                  className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
                  size="lg"
                >
                  Start Focus Session
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex flex-col items-center justify-center py-12">
                  <p className="text-slate-400 text-sm mb-4">Time Remaining</p>
                  <div className="text-7xl font-bold text-emerald-400 font-mono">
                    {formatTime(timeRemaining)}
                  </div>
                </div>
                <Button
                  onClick={endFocus}
                  className="w-full bg-red-600 hover:bg-red-700 text-white"
                  size="lg"
                >
                  End Session
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={showFeedbackDialog} onOpenChange={setShowFeedbackDialog}>
        <DialogContent className="bg-slate-800 border-slate-700 text-white">
          <DialogHeader>
            <DialogTitle>Session Feedback</DialogTitle>
            <DialogDescription className="text-slate-400">
              How productive was this session?
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <label className="block text-sm font-medium mb-3">Rating</label>
              <div className="flex gap-2">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    onClick={() => setRating(star)}
                    className={`text-3xl transition-all ${
                      rating === star ? 'scale-110' : 'scale-100 opacity-50'
                    }`}
                  >
                    ★
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label htmlFor="notes" className="block text-sm font-medium mb-2">
                Notes (optional)
              </label>
              <Textarea
                id="notes"
                placeholder="What went well? Any challenges?"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="bg-slate-700 border-slate-600 text-white"
                rows={4}
              />
            </div>
            <Button
              onClick={submitFeedback}
              disabled={rating === null || isFeedbackLoading}
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {isFeedbackLoading ? 'Submitting...' : 'Submit Feedback'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
