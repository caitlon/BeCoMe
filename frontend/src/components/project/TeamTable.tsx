import { useTranslation } from "react-i18next";
import { Crown, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Member, ProjectInvitation } from "@/types/api";

export interface TeamTableProps {
  members: Member[];
  pendingInvitations: ProjectInvitation[];
  isAdmin: boolean;
  currentUserId?: string;
  selectedMemberId?: string;
  onRemove: (userId: string) => void;
  onTransfer: (member: Member) => void;
  onMemberClick: (member: Member) => void;
}

export const TeamTable = ({
  members,
  pendingInvitations,
  isAdmin,
  currentUserId,
  selectedMemberId,
  onRemove,
  onTransfer,
  onMemberClick,
}: TeamTableProps) => {
  const { t, i18n } = useTranslation("projects");
  const { t: tCommon } = useTranslation();

  return (
    <Card>
      <CardContent className="pt-6">
        <Table>
          <TableCaption className="sr-only">{tCommon("a11y.teamMembers")}</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>{t("team.name")}</TableHead>
              <TableHead>{t("team.email")}</TableHead>
              <TableHead>{t("team.role")}</TableHead>
              <TableHead>{t("team.joined")}</TableHead>
              {isAdmin && <TableHead></TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {members.map((member) => {
              const fullName = `${member.first_name} ${member.last_name ?? ""}`.trim();
              return (
                <TableRow
                  key={member.user_id}
                  className="cursor-pointer hover:bg-muted/50 transition-colors"
                  onClick={() => onMemberClick(member)}
                  role="button"
                  tabIndex={0}
                  aria-label={t("memberProfile.viewProfile", { name: fullName })}
                  aria-current={selectedMemberId === member.user_id ? "true" : undefined}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onMemberClick(member);
                    }
                  }}
                >
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <Avatar className="h-7 w-7" aria-hidden="true">
                        {member.photo_url && (
                          <AvatarImage src={member.photo_url} alt="" />
                        )}
                        <AvatarFallback className="text-xs">
                          {`${member.first_name[0]}${member.last_name?.[0] || ""}`.toUpperCase()}
                        </AvatarFallback>
                      </Avatar>
                      <span>{fullName}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {member.email}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={member.role === "admin" ? "default" : "secondary"}
                    >
                      {t(`roles.${member.role}`)}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(member.joined_at).toLocaleDateString(i18n.language)}
                  </TableCell>
                  {isAdmin && (
                    <TableCell>
                      {member.role !== "admin" &&
                        member.user_id !== currentUserId && (
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={(e) => {
                                e.stopPropagation();
                                onTransfer(member);
                              }}
                              aria-label={t("team.transferOwnershipLabel", { name: fullName })}
                            >
                              <Crown className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 text-destructive hover:text-destructive"
                              onClick={(e) => {
                                e.stopPropagation();
                                onRemove(member.user_id);
                              }}
                              aria-label={tCommon("a11y.removeTeamMember", { name: fullName })}
                            >
                              <X className="h-4 w-4" />
                            </Button>
                          </div>
                        )}
                    </TableCell>
                  )}
                </TableRow>
              );
            })}
            {pendingInvitations.map((inv) => {
              const fullName = `${inv.invitee_first_name} ${inv.invitee_last_name ?? ""}`.trim();
              return (
                <TableRow key={inv.id} className="opacity-50">
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <Avatar className="h-7 w-7" aria-hidden="true">
                        <AvatarFallback className="text-xs">
                          {`${inv.invitee_first_name[0]}${inv.invitee_last_name?.[0] || ""}`.toUpperCase()}
                        </AvatarFallback>
                      </Avatar>
                      <span>
                        <span className="sr-only">{tCommon("a11y.pendingInvitationRow", { name: fullName })}</span>
                        {fullName}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {inv.invitee_email}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {t("roles.invited")}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground"><span aria-hidden="true">—</span><span className="sr-only">{tCommon("a11y.noDataAvailable")}</span></TableCell>
                  {isAdmin && <TableCell />}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
};
