import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { SubmitButton } from "@/components/forms";

interface DeleteConfirmModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  details?: string[];
  onConfirm: () => Promise<void>;
  confirmText?: string;
  loadingText?: string;
}

export function DeleteConfirmModal({
  open,
  onOpenChange,
  title,
  description,
  details,
  onConfirm,
  confirmText = "Delete Project",
  loadingText = "Deleting...",
}: DeleteConfirmModalProps) {
  const [isLoading, setIsLoading] = useState(false);

  const handleConfirm = async () => {
    setIsLoading(true);
    try {
      await onConfirm();
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            {title}
          </DialogTitle>
        </DialogHeader>

        <div className="py-4">
          <p className="text-muted-foreground mb-4">{description}</p>

          {details && details.length > 0 && (
            <div className="bg-muted p-4 rounded-lg mb-4">
              <p className="text-sm font-medium mb-2">This will permanently delete:</p>
              <ul className="text-sm text-muted-foreground space-y-1">
                {details.map((detail, index) => (
                  <li key={index}>• {detail}</li>
                ))}
              </ul>
            </div>
          )}

          <p className="text-sm font-medium text-destructive">
            This action cannot be undone.
          </p>
        </div>

        <div className="flex justify-end gap-3">
          <Button 
            variant="outline" 
            onClick={() => onOpenChange(false)}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <SubmitButton
            type="button"
            variant="destructive"
            onClick={handleConfirm}
            isLoading={isLoading}
            loadingText={loadingText}
          >
            {confirmText}
          </SubmitButton>
        </div>
      </DialogContent>
    </Dialog>
  );
}
