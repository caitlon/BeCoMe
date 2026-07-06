import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Opinion, Member } from "@/types/api";

export interface OtherOpinionsTableProps {
  opinions: Opinion[];
  members: Member[];
  currentUserId?: string;
}

export const OtherOpinionsTable = ({
  opinions,
  members,
  currentUserId,
}: OtherOpinionsTableProps) => {
  const { t } = useTranslation("projects");
  const { t: tFuzzy } = useTranslation();

  const opinionUserIds = new Set(opinions.map((o) => o.user_id));
  const pendingMembers = members.filter(
    (m) => m.user_id !== currentUserId && !opinionUserIds.has(m.user_id)
  );

  if (opinions.length === 0 && pendingMembers.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t("detail.otherOpinions")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-center py-8">
            {t("detail.noOtherOpinions")}
          </p>
        </CardContent>
      </Card>
    );
  }

  const sorted = [...opinions].sort((a, b) => b.centroid - a.centroid);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{t("detail.otherOpinions")}</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableCaption className="sr-only">{tFuzzy("a11y.expertOpinions")}</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>{t("detail.expert")}</TableHead>
              <TableHead className="text-right font-mono">L</TableHead>
              <TableHead className="text-right font-mono">P</TableHead>
              <TableHead className="text-right font-mono">U</TableHead>
              <TableHead className="text-right font-mono">{tFuzzy("fuzzy.centroid")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((opinion) => (
              <TableRow key={opinion.id}>
                <TableCell>
                  <div>
                    <div className="font-medium">
                      {opinion.user_first_name} {opinion.user_last_name}
                    </div>
                    {opinion.position && (
                      <div className="text-xs text-muted-foreground">
                        {opinion.position}
                      </div>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-right font-mono">
                  {opinion.lower_bound}
                </TableCell>
                <TableCell className="text-right font-mono">
                  {opinion.peak}
                </TableCell>
                <TableCell className="text-right font-mono">
                  {opinion.upper_bound}
                </TableCell>
                <TableCell className="text-right font-mono font-medium">
                  {opinion.centroid.toFixed(2)}
                </TableCell>
              </TableRow>
            ))}
            {pendingMembers.map((member) => {
              const fullName = `${member.first_name} ${member.last_name ?? ""}`.trim();
              return (
                <TableRow key={member.user_id} className="opacity-50">
                  <TableCell>
                    <div>
                      <span className="sr-only">{tFuzzy("a11y.pendingMemberRow", { name: fullName })}</span>
                      <div className="font-medium">
                        {fullName}
                      </div>
                      <div className="text-xs text-muted-foreground italic">
                        {t("detail.awaitingResponse")}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground"><span aria-hidden="true">—</span><span className="sr-only">{tFuzzy("a11y.noDataAvailable")}</span></TableCell>
                  <TableCell className="text-right text-muted-foreground"><span aria-hidden="true">—</span><span className="sr-only">{tFuzzy("a11y.noDataAvailable")}</span></TableCell>
                  <TableCell className="text-right text-muted-foreground"><span aria-hidden="true">—</span><span className="sr-only">{tFuzzy("a11y.noDataAvailable")}</span></TableCell>
                  <TableCell className="text-right text-muted-foreground"><span aria-hidden="true">—</span><span className="sr-only">{tFuzzy("a11y.noDataAvailable")}</span></TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
};
