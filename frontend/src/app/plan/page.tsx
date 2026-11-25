import Link from "next/link";
import { Utensils } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function PlanPlaceholderPage() {
  return (
    <Card>
      <CardHeader>
        <Badge variant="amber" className="w-fit">
          Coming in Module 3.4
        </Badge>
        <div className="mt-2 flex items-center gap-2.5">
          <Utensils className="h-6 w-6 text-[#d97706]" />
          <CardTitle>Daily & Weekly Pakistani Meal Planner</CardTitle>
        </div>
        <CardDescription>
          Verified desi meal plans, meal swaps, aur consolidated grocery checklist Module 3.4 mein
          yahan show honge.
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
