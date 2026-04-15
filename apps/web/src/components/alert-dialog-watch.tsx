"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { apiClient } from "@/lib/api";
import type { FacilityResult, WatchResponse } from "@/lib/types";

interface Props {
  facility: FacilityResult;
  dateStart: string;
  dateEnd: string;
  nights: number;
  token: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function AlertDialogWatch({
  facility,
  dateStart,
  dateEnd,
  nights,
  token,
  open,
  onOpenChange,
  onSuccess,
}: Props) {
  const defaultName = `Alert: ${facility.name}`;
  const [name, setName] = useState(defaultName);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await apiClient<WatchResponse>("/api/watches", {
        method: "POST",
        token,
        body: JSON.stringify({
          name,
          facility_id: facility.id,
          date_start: dateStart,
          date_end: dateEnd,
          nights,
        }),
      });
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create alert");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create availability alert</DialogTitle>
          <DialogDescription>
            Get notified when {facility.name} has openings for {dateStart} to {dateEnd}.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="watch-name">Alert name</Label>
            <Input
              id="watch-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="rounded-md bg-muted p-3 text-sm">
            <p><span className="font-medium">Campground:</span> {facility.name}</p>
            <p><span className="font-medium">Dates:</span> {dateStart} to {dateEnd}</p>
            <p><span className="font-medium">Nights:</span> {nights}</p>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <Button type="submit" disabled={loading} className="w-full">
            {loading ? "Creating..." : "Create alert"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
