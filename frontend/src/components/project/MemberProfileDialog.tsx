import { useTranslation } from "react-i18next";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Member, Opinion } from "@/types/api";

export interface MemberProfileDialogProps {
  member: Member | null;
  opinion: Opinion | null;
  onOpenChange: (open: boolean) => void;
}

export const MemberProfileDialog = ({
  member,
  opinion,
  onOpenChange,
}: MemberProfileDialogProps) => {
  const { t, i18n } = useTranslation("projects");
  const { t: tCommon } = useTranslation();

  if (!member) return null;

  const fullName = `${member.first_name} ${member.last_name ?? ""}`.trim();
  const initials = `${member.first_name[0]}${member.last_name?.[0] || ""}`.toUpperCase();

  return (
    <Dialog open={!!member} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader className="items-center text-center">
          <Avatar className="h-20 w-20 mb-2">
            {member.photo_url && (
              <AvatarImage src={member.photo_url} alt={fullName} />
            )}
            <AvatarFallback className="text-xl">{initials}</AvatarFallback>
          </Avatar>
          <DialogTitle className="text-xl font-light">{fullName}</DialogTitle>
          <div className="flex flex-col items-center gap-1">
            <Badge
              variant={member.role === "admin" ? "default" : "secondary"}
              aria-hidden="true"
            >
              {t(`roles.${member.role}`)}
            </Badge>
          </div>
          <DialogDescription className="sr-only">
            {t("memberProfile.dialogDescription")}
          </DialogDescription>
        </DialogHeader>

        <Separator />

        <div className="space-y-4">
          {opinion?.position && (
            <div>
              <p className="text-sm text-muted-foreground">
                {t("memberProfile.position")}
              </p>
              <p className="font-medium">{opinion.position}</p>
            </div>
          )}

          <div>
            <p className="text-sm text-muted-foreground mb-2">
              {t("memberProfile.opinion")}
            </p>
            {opinion ? (
              <>
                <span className="sr-only">
                  {tCommon("a11y.opinionValues", {
                    lower: opinion.lower_bound.toFixed(2),
                    peak: opinion.peak.toFixed(2),
                    upper: opinion.upper_bound.toFixed(2),
                    centroid: opinion.centroid.toFixed(2),
                  })}
                </span>
                <div className="grid grid-cols-4 gap-3 text-center" aria-hidden="true">
                  <div>
                    <div className="text-xs text-muted-foreground">
                      {tCommon("fuzzy.lower")}
                    </div>
                    <div className="font-mono font-medium">
                      {opinion.lower_bound.toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">
                      {tCommon("fuzzy.peak")}
                    </div>
                    <div className="font-mono font-medium">
                      {opinion.peak.toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">
                      {tCommon("fuzzy.upper")}
                    </div>
                    <div className="font-mono font-medium">
                      {opinion.upper_bound.toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">
                      {tCommon("fuzzy.centroid")}
                    </div>
                    <div className="font-mono font-medium">
                      {opinion.centroid.toFixed(2)}
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground italic">
                {t("memberProfile.noOpinion")}
              </p>
            )}
          </div>

          <div>
            <p className="text-sm text-muted-foreground">
              {t("memberProfile.joined")}
            </p>
            <p className="text-sm">
              {new Date(member.joined_at).toLocaleDateString(i18n.language)}
            </p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
