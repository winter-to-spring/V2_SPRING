'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { getLatestBriefing, generateBriefing } from '@/lib/briefing-api';

interface Briefing {
  id: string;
  content: string;
  generated_at: string;
  kind: string;
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

interface MarkdownNode {
  type: 'paragraph' | 'bullet-list' | 'bullet-item';
  content?: string;
  items?: string[];
}

function parseSimpleMarkdown(content: string): MarkdownNode[] {
  const lines = content.split('\n');
  const nodes: MarkdownNode[] = [];
  let currentBulletList: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();

    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      currentBulletList.push(trimmed.substring(2));
    } else if (trimmed.length > 0) {
      if (currentBulletList.length > 0) {
        nodes.push({
          type: 'bullet-list',
          items: currentBulletList,
        });
        currentBulletList = [];
      }
      nodes.push({
        type: 'paragraph',
        content: trimmed,
      });
    }
  }

  if (currentBulletList.length > 0) {
    nodes.push({
      type: 'bullet-list',
      items: currentBulletList,
    });
  }

  return nodes;
}

function MarkdownRenderer({ content }: { content: string }) {
  const nodes = parseSimpleMarkdown(content);

  return (
    <div className="space-y-3">
      {nodes.map((node, idx) => {
        if (node.type === 'paragraph') {
          return (
            <p key={idx} className="text-sm leading-relaxed text-gray-700">
              {node.content}
            </p>
          );
        }
        if (node.type === 'bullet-list') {
          return (
            <ul key={idx} className="list-disc list-inside space-y-1 text-sm text-gray-700">
              {node.items?.map((item, itemIdx) => (
                <li key={itemIdx}>{item}</li>
              ))}
            </ul>
          );
        }
        return null;
      })}
    </div>
  );
}

export default function BriefingPage() {
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchBriefing = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getLatestBriefing();
        setBriefing(data);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to fetch briefing';
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    fetchBriefing();
  }, []);

  const handleGenerateNew = async () => {
    setGenerating(true);
    setError(null);
    try {
      await generateBriefing({ kind: 'manual' });
      // Refresh the briefing
      const data = await getLatestBriefing();
      setBriefing(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to generate briefing';
      setError(message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="container mx-auto py-8 px-4">
      <h1 className="text-3xl font-bold mb-6">Daily Briefing</h1>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-md text-red-800">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-center text-gray-500">Loading briefing...</div>
      ) : briefing ? (
        <Card className="p-6">
          <div className="flex items-start justify-between mb-4">
            <h2 className="text-lg font-semibold">Latest Briefing</h2>
            <span className="text-xs text-gray-500">
              Generated {formatRelativeTime(briefing.generated_at)}
            </span>
          </div>

          <div className="mb-6 border-t pt-4">
            <MarkdownRenderer content={briefing.content} />
          </div>

          <div className="flex justify-end">
            <Button
              onClick={handleGenerateNew}
              disabled={generating}
              variant="default"
            >
              {generating ? 'Generating...' : 'Generate New'}
            </Button>
          </div>
        </Card>
      ) : (
        <Card className="p-6 text-center">
          <p className="text-gray-600 mb-4">
            No briefing yet — start a focus session or click Generate New
          </p>
          <Button
            onClick={handleGenerateNew}
            disabled={generating}
            variant="default"
          >
            {generating ? 'Generating...' : 'Generate New'}
          </Button>
        </Card>
      )}
    </div>
  );
}
