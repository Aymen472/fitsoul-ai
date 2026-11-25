import Link from "next/link";
import { Dumbbell } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function WorkoutsPlaceholderPage() {
  return (
    <Card>
      <CardHeader>
        <Badge variant="teal" className="w-fit">
          Coming in Module 3.5
        </Badge>
        <div className="mt-2 flex items-center gap-2.5">
          <Dumbbell className="h-6 w-6 text-[#0f766e]" />
          <CardTitle>Guided Workouts & Face Yoga Player</CardTitle>
        </div>
        <CardDescription>
          Exercise library, countdown timer, rest intervals, aur MET calorie logging Module 3.5
          mein yahan launch hoga.
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
