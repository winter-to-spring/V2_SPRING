'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';

interface SlackInstallResponse {
  installUrl: string;
}

export default function IntegrationsPage() {
  const searchParams = useSearchParams();
  const { toast } = useToast();
  
  const [slackConnected, setSlackConnected] = useState(false);
  const [slackWorkspace, setSlackWorkspace] = useState<string | null>(null);
  const [isLoadingSlack, setIsLoadingSlack] = useState(false);

  useEffect(() => {
    // Check for installation success toast
    const installed = searchParams.get('installed');
    if (installed === 'slack') {
      toast({
        title: 'Success',
        description: 'Slack workspace connected successfully.',
        variant: 'default',
      });
      setSlackConnected(true);
      setSlackWorkspace('Workspace');
    }
  }, [searchParams, toast]);

  const handleConnectSlack = async () => {
    try {
      setIsLoadingSlack(true);
      const response = await fetch('/api/integrations/slack/install-url', {
        method: 'GET',
      });
      
      if (!response.ok) {
        throw new Error('Failed to get Slack install URL');
      }
      
      const data: SlackInstallResponse = await response.json();
      window.location.assign(data.installUrl);
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to connect Slack. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setIsLoadingSlack(false);
    }
  };

  const handleDisconnectSlack = () => {
    // Stub for disconnect functionality
    console.log('Disconnect Slack clicked');
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Integrations</h1>
        <p className="text-sm text-muted-foreground mt-2">
          Connect your workspace with external services.
        </p>
      </div>

      <div className="grid gap-6">
        {/* Slack Card */}
        <Card className="border border-slate-800 bg-slate-950 text-slate-50">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <CardTitle>Slack</CardTitle>
                  {slackConnected && (
                    <Badge variant="default" className="bg-green-900 text-green-100">
                      Connected
                    </Badge>
                  )}
                </div>
              </div>
            </div>
            <CardDescription className="text-slate-400">
              Connect your Slack workspace to receive notifications and manage integrations.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {slackConnected ? (
              <div className="space-y-4">
                <div>
                  <p className="text-sm text-slate-400">Workspace</p>
                  <p className="font-semibold">{slackWorkspace}</p>
                </div>
                <Button
                  onClick={handleDisconnectSlack}
                  disabled
                  variant="outline"
                  className="border-slate-700 text-slate-400 hover:bg-slate-900 hover:text-slate-400 cursor-not-allowed"
                >
                  Disconnect
                </Button>
              </div>
            ) : (
              <Button
                onClick={handleConnectSlack}
                disabled={isLoadingSlack}
                className="w-full bg-slate-700 hover:bg-slate-600 text-slate-50"
              >
                {isLoadingSlack ? 'Connecting...' : 'Connect Slack'}
              </Button>
            )}
          </CardContent>
        </Card>

        {/* Discord Card - Coming Soon */}
        <Card className="border border-slate-800 bg-slate-950 text-slate-50 opacity-60">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CardTitle>Discord</CardTitle>
                <Badge variant="secondary" className="bg-slate-800 text-slate-300">
                  Coming soon
                </Badge>
              </div>
            </div>
            <CardDescription className="text-slate-400">
              Integrate Discord for team communication and notifications.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              disabled
              className="w-full bg-slate-700 text-slate-500 cursor-not-allowed"
            >
              Coming soon
            </Button>
          </CardContent>
        </Card>

        {/* Gmail Card - Coming Soon */}
        <Card className="border border-slate-800 bg-slate-950 text-slate-50 opacity-60">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CardTitle>Gmail</CardTitle>
                <Badge variant="secondary" className="bg-slate-800 text-slate-300">
                  Coming soon
                </Badge>
              </div>
            </div>
            <CardDescription className="text-slate-400">
              Sync emails and calendar events with your workspace.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              disabled
              className="w-full bg-slate-700 text-slate-500 cursor-not-allowed"
            >
              Coming soon
            </Button>
          </CardContent>
        </Card>

        {/* Jira Card - Coming Soon */}
        <Card className="border border-slate-800 bg-slate-950 text-slate-50 opacity-60">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CardTitle>Jira</CardTitle>
                <Badge variant="secondary" className="bg-slate-800 text-slate-300">
                  Coming soon
                </Badge>
              </div>
            </div>
            <CardDescription className="text-slate-400">
              Connect Jira for issue tracking and project management.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              disabled
              className="w-full bg-slate-700 text-slate-500 cursor-not-allowed"
            >
              Coming soon
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
