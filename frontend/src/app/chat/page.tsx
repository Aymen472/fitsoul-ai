import Link from "next/link";
import { MessageCircleHeart } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function ChatPlaceholderPage() {
  return (
    <Card>
      <CardHeader>
        <Badge variant="teal" className="w-fit">
          Coming in Module 3.2
        </Badge>
        <div className="mt-2 flex items-center gap-2.5">
          <MessageCircleHeart className="h-6 w-6 text-[#0f766e]" />
          <CardTitle>AI Coach Chat & Persistent History</CardTitle>
        </div>
        <CardDescription>
          Full bilingual chat UI wired directly to <code>POST /api/v1/chat</code>,{" "}
          <code>/history</code>, and <code>/patterns</code> will be built in the very next module!
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Link href="/">
          <Button variant="outline">Back to Wellness Hub</Button>
        </Link>
      </CardContent>
    </Card>
  );
}
