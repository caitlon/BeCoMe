import { useState, useEffect, useCallback } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Loader2,
  Users,
  Edit,
  UserPlus,
  Trash2,
  ChevronDown,
  ChevronUp,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Navbar } from "@/components/layout/Navbar";
import { SubmitButton } from "@/components/forms";
import { InviteExpertModal } from "@/components/modals/InviteExpertModal";
import { DeleteConfirmModal } from "@/components/modals/DeleteConfirmModal";
import { api } from "@/lib/api";
import { ProjectWithRole, Opinion, CalculationResult, Member, ProjectInvitation } from "@/types/api";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { CentroidBarChart } from "@/components/visualizations/CentroidBarChart";
import { cn } from "@/lib/utils";

const ProjectDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { toast } = useToast();
  const { t } = useTranslation("projects");
  const { t: tCommon } = useTranslation();

  const [project, setProject] = useState<ProjectWithRole | null>(null);
  const [opinions, setOpinions] = useState<Opinion[]>([]);
  const [result, setResult] = useState<CalculationResult | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [pendingInvitations, setPendingInvitations] = useState<ProjectInvitation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSavingOpinion, setIsSavingOpinion] = useState(false);

  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [teamOpen, setTeamOpen] = useState(true);
  const [showIndividual, setShowIndividual] = useState(false);
  const [profileMember, setProfileMember] = useState<Member | null>(null);

  // Opinion form state
  const [position, setPosition] = useState("");
  const [lower, setLower] = useState("");
  const [peak, setPeak] = useState("");
  const [upper, setUpper] = useState("");
  useDocumentTitle(project ? tCommon("pageTitle.projectDetail", { name: project.name }) : tCommon("common.loading"));

  const myOpinion = opinions.find((o) => o.user_id === user?.id);
  const otherOpinions = opinions.filter((o) => o.user_id !== user?.id);
  const isAdmin = project?.role === "admin";
  const profileOpinion = profileMember
    ? opinions.find((o) => o.user_id === profileMember.user_id) ?? null
    : null;

  const fetchData = useCallback(async () => {
    if (!id) return;
    try {
      const [projectData, opinionsData, resultData, membersData, invitationsData] =
        await Promise.all([
          api.getProject(id),
          api.getOpinions(id),
          api.getResult(id),
          api.getMembers(id),
          api.getProjectInvitations(id).catch(() => [] as ProjectInvitation[]),
        ]);
      setProject(projectData);
      setOpinions(opinionsData);
      setResult(resultData);
      setMembers(membersData);
      setPendingInvitations(invitationsData);

      // Pre-fill form if user has opinion
      const existing = opinionsData.find((o) => o.user_id === user?.id);
      if (existing) {
        setPosition(existing.position || "");
        setLower(String(existing.lower_bound));
        setPeak(String(existing.peak));
        setUpper(String(existing.upper_bound));
      }
    } catch (error) {
      toast({
        title: t("toast.error"),
        description: t("toast.loadProjectFailed"),
        variant: "destructive",
      });
      navigate("/projects");
    } finally {
      setIsLoading(false);
    }
  }, [id, user?.id, toast, navigate, t]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSaveOpinion = async () => {
    if (!id || !project) return;

    const lowerNum = parseFloat(lower);
    const peakNum = parseFloat(peak);
    const upperNum = parseFloat(upper);

    // Validation
    if (isNaN(lowerNum) || isNaN(peakNum) || isNaN(upperNum)) {
      toast({
        title: t("toast.validationError"),
        description: t("toast.invalidNumbers"),
        variant: "destructive",
      });
      return;
    }

    if (lowerNum > peakNum || peakNum > upperNum) {
      toast({
        title: t("toast.validationError"),
        description: t("toast.lowerPeakUpper"),
        variant: "destructive",
      });
      return;
    }

    if (lowerNum < project.scale_min || upperNum > project.scale_max) {
      toast({
        title: t("toast.validationError"),
        description: t("toast.scaleRange", { min: project.scale_min, max: project.scale_max }),
        variant: "destructive",
      });
      return;
    }

    setIsSavingOpinion(true);
    try {
      await api.createOrUpdateOpinion(id, {
        position,
        lower_bound: lowerNum,
        peak: peakNum,
        upper_bound: upperNum,
      });
      toast({ title: t("toast.opinionSaved") });
      fetchData();
    } catch (error) {
      toast({
        title: t("toast.error"),
        description: error instanceof Error ? error.message : t("toast.saveFailed"),
        variant: "destructive",
      });
    } finally {
      setIsSavingOpinion(false);
    }
  };

  const handleDeleteOpinion = async () => {
    if (!id) return;
    try {
      await api.deleteOpinion(id);
      setPosition("");
      setLower("");
      setPeak("");
      setUpper("");
      toast({ title: t("toast.opinionDeleted") });
      fetchData();
    } catch (error) {
      toast({
        title: t("toast.error"),
        description: t("toast.deleteOpinionFailed"),
        variant: "destructive",
      });
    }
  };

  const handleDeleteProject = async () => {
    if (!id) return;
    try {
      await api.deleteProject(id);
      toast({ title: t("toast.projectDeleted") });
      navigate("/projects");
    } catch (error) {
      toast({
        title: t("toast.error"),
        description: t("toast.deleteFailed"),
        variant: "destructive",
      });
    }
  };

  const handleRemoveMember = async (userId: string) => {
    if (!id) return;
    try {
      await api.removeMember(id, userId);
      toast({ title: t("toast.memberRemoved") });
      fetchData();
    } catch (error) {
      toast({
        title: t("toast.error"),
        description: t("toast.removeMemberFailed"),
        variant: "destructive",
      });
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen">
        <Navbar />
        <main id="main-content" className="pt-24 flex items-center justify-center">
          <div role="status" aria-label={tCommon("a11y.loading")}>
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <span className="sr-only">{tCommon("common.loading")}</span>
          </div>
        </main>
      </div>
    );
  }

  if (!project) {
    return null;
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <main id="main-content" className="container mx-auto px-6 pt-24 pb-16">
        {/* Breadcrumb */}
        <div className="mb-6">
          <Link
            to="/projects"
            className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            {t("detail.projects")}
          </Link>
        </div>

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="font-display text-3xl md:text-4xl font-light mb-2">
            {project.name}
          </h1>
          {project.description && (
            <p className="text-muted-foreground mb-4">{project.description}</p>
          )}
          <div className="flex flex-wrap items-center gap-4">
            <span className="font-mono text-sm bg-muted px-3 py-1 rounded">
              {t("detail.scale")}: {project.scale_min} — {project.scale_max} {project.scale_unit}
            </span>
            {isAdmin && (
              <div className="flex gap-2">
                <Button variant="outline" size="sm" className="gap-2">
                  <Edit className="h-4 w-4" />
                  {t("detail.edit")}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => setInviteModalOpen(true)}
                >
                  <UserPlus className="h-4 w-4" />
                  {t("detail.inviteExperts")}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2 text-destructive hover:text-destructive"
                  onClick={() => setDeleteModalOpen(true)}
                >
                  <Trash2 className="h-4 w-4" />
                  {t("detail.delete")}
                </Button>
              </div>
            )}
          </div>
        </motion.div>

        {/* Main Content - Two Columns on Desktop */}
        <div className="hidden lg:grid lg:grid-cols-2 gap-8">
          {/* Left Column - Opinions */}
          <div className="space-y-6">
            <OpinionForm
              position={position}
              setPosition={setPosition}
              lower={lower}
              setLower={setLower}
              peak={peak}
              setPeak={setPeak}
              upper={upper}
              setUpper={setUpper}
              project={project}
              myOpinion={myOpinion}
              isSaving={isSavingOpinion}
              onSave={handleSaveOpinion}
              onDelete={handleDeleteOpinion}
            />

            <OtherOpinionsTable opinions={otherOpinions} members={members} currentUserId={user?.id} />
          </div>

          {/* Right Column - Results */}
          <div className="space-y-6">
            <ResultsSection
              result={result}
              project={project}
              showIndividual={showIndividual}
              setShowIndividual={setShowIndividual}
              opinions={opinions}
            />
          </div>
        </div>

        {/* Mobile - Tabs */}
        <div className="lg:hidden">
          <Tabs defaultValue="opinions" className="space-y-6">
            <TabsList className="w-full">
              <TabsTrigger value="opinions" className="flex-1">
                {t("detail.opinions")}
              </TabsTrigger>
              <TabsTrigger value="results" className="flex-1">
                {t("detail.results")}
              </TabsTrigger>
              <TabsTrigger value="team" className="flex-1">
                {t("detail.team")}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="opinions" className="space-y-6">
              <OpinionForm
                position={position}
                setPosition={setPosition}
                lower={lower}
                setLower={setLower}
                peak={peak}
                setPeak={setPeak}
                upper={upper}
                setUpper={setUpper}
                project={project}
                myOpinion={myOpinion}
                isSaving={isSavingOpinion}
                onSave={handleSaveOpinion}
                onDelete={handleDeleteOpinion}
              />
              <OtherOpinionsTable opinions={otherOpinions} members={members} currentUserId={user?.id} />
            </TabsContent>

            <TabsContent value="results">
              <ResultsSection
                result={result}
                project={project}
                showIndividual={showIndividual}
                setShowIndividual={setShowIndividual}
                opinions={opinions}
              />
            </TabsContent>

            <TabsContent value="team">
              <TeamTable
                members={members}
                pendingInvitations={pendingInvitations}
                isAdmin={isAdmin}
                currentUserId={user?.id}
                selectedMemberId={profileMember?.user_id}
                onRemove={handleRemoveMember}
                onMemberClick={(member) => setProfileMember(member)}
              />
            </TabsContent>
          </Tabs>
        </div>

        {/* Team Section - Desktop Collapsible */}
        <div className="hidden lg:block mt-8">
          <Collapsible open={teamOpen} onOpenChange={setTeamOpen}>
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                className="w-full justify-between p-4 h-auto bg-muted rounded-lg hover:bg-muted/70"
              >
                <span className="flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  {t("detail.teamMembers", { count: members.length })}
                </span>
                {teamOpen ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <TeamTable
                members={members}
                pendingInvitations={pendingInvitations}
                isAdmin={isAdmin}
                currentUserId={user?.id}
                selectedMemberId={profileMember?.user_id}
                onRemove={handleRemoveMember}
                onMemberClick={(member) => setProfileMember(member)}
              />
            </CollapsibleContent>
          </Collapsible>
        </div>
      </main>

      <InviteExpertModal
        open={inviteModalOpen}
        onOpenChange={setInviteModalOpen}
        projectId={project.id}
        projectName={project.name}
      />

      <DeleteConfirmModal
        open={deleteModalOpen}
        onOpenChange={setDeleteModalOpen}
        title={t("deleteModal.title")}
        description={t("deleteModal.description", { name: project.name })}
        details={[
          t("deleteModal.details.opinions", { count: opinions.length }),
          t("deleteModal.details.results"),
          t("deleteModal.details.invitations"),
        ]}
        onConfirm={handleDeleteProject}
      />

      <MemberProfileDialog
        member={profileMember}
        opinion={profileOpinion}
        onOpenChange={(open) => !open && setProfileMember(null)}
      />
    </div>
  );
};

// Sub-components

interface OpinionFormProps {
  position: string;
  setPosition: (v: string) => void;
  lower: string;
  setLower: (v: string) => void;
  peak: string;
  setPeak: (v: string) => void;
  upper: string;
  setUpper: (v: string) => void;
  project: ProjectWithRole;
  myOpinion?: Opinion;
  isSaving: boolean;
  onSave: () => void;
  onDelete: () => void;
}

const OpinionForm = ({
  position,
  setPosition,
  lower,
  setLower,
  peak,
  setPeak,
  upper,
  setUpper,
  project,
  myOpinion,
  isSaving,
  onSave,
  onDelete,
}: OpinionFormProps) => {
  const { t } = useTranslation("projects");
  const { t: tFuzzy } = useTranslation();
  const lowerNum = parseFloat(lower) || 0;
  const peakNum = parseFloat(peak) || 0;
  const upperNum = parseFloat(upper) || 0;
  const isValid =
    lowerNum <= peakNum &&
    peakNum <= upperNum &&
    lowerNum >= project.scale_min &&
    upperNum <= project.scale_max;
  const hasChanges = !myOpinion ||
    position !== (myOpinion.position || "") ||
    lower !== String(myOpinion.lower_bound) ||
    peak !== String(myOpinion.peak) ||
    upper !== String(myOpinion.upper_bound);

  return (
    <Card className="border-2 border-primary/20" aria-busy={isSaving}>
      <CardHeader>
        <CardTitle className="text-lg">{t("detail.yourOpinion")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <Label htmlFor="position">{t("detail.position")}</Label>
          <Input
            id="position"
            required
            placeholder={t("detail.positionPlaceholder")}
            value={position}
            onChange={(e) => setPosition(e.target.value)}
          />
        </div>

        <fieldset>
          <legend className="text-sm font-medium leading-none mb-2">{t("detail.yourEstimate")}</legend>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label htmlFor="opinion-lower" className="text-xs text-muted-foreground">
                {tFuzzy("fuzzy.lowerDesc")}
              </Label>
              <Input
                id="opinion-lower"
                type="number"
                required
                placeholder={String(project.scale_min)}
                value={lower}
                onChange={(e) => setLower(e.target.value)}
                className="font-mono"
              />
            </div>
            <div>
              <Label htmlFor="opinion-peak" className="text-xs text-muted-foreground">
                {tFuzzy("fuzzy.peakDesc")}
              </Label>
              <Input
                id="opinion-peak"
                type="number"
                required
                value={peak}
                onChange={(e) => setPeak(e.target.value)}
                className="font-mono"
              />
            </div>
            <div>
              <Label htmlFor="opinion-upper" className="text-xs text-muted-foreground">
                {tFuzzy("fuzzy.upperDesc")}
              </Label>
              <Input
                id="opinion-upper"
                type="number"
                required
                placeholder={String(project.scale_max)}
                value={upper}
                onChange={(e) => setUpper(e.target.value)}
                className="font-mono"
              />
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            {t("detail.range")}: {project.scale_min} — {project.scale_max} {project.scale_unit}
          </p>
        </fieldset>

        {/* Mini Triangle Preview */}
        {lower && peak && upper && isValid && (
          <div className="bg-muted rounded p-4">
            <svg viewBox="0 0 200 60" className="w-full h-12" role="img" aria-label={tFuzzy("a11y.opinionPreviewDesc", { lower: lowerNum, peak: peakNum, upper: upperNum })}>
              <line
                x1="10"
                y1="50"
                x2="190"
                y2="50"
                stroke="currentColor"
                strokeOpacity="0.2"
              />
              <polygon
                points={`${10 + ((lowerNum - project.scale_min) / (project.scale_max - project.scale_min)) * 180},50 ${10 + ((peakNum - project.scale_min) / (project.scale_max - project.scale_min)) * 180},10 ${10 + ((upperNum - project.scale_min) / (project.scale_max - project.scale_min)) * 180},50`}
                fill="currentColor"
                fillOpacity="0.1"
                stroke="currentColor"
                strokeWidth="1.5"
              />
              <text
                x={
                  10 +
                  ((lowerNum - project.scale_min) /
                    (project.scale_max - project.scale_min)) *
                    180
                }
                y="58"
                className="fill-muted-foreground"
                fontSize="8"
                textAnchor="middle"
              >
                {lowerNum}
              </text>
              <text
                x={
                  10 +
                  ((peakNum - project.scale_min) /
                    (project.scale_max - project.scale_min)) *
                    180
                }
                y="8"
                className="fill-muted-foreground"
                fontSize="8"
                textAnchor="middle"
              >
                {peakNum}
              </text>
              <text
                x={
                  10 +
                  ((upperNum - project.scale_min) /
                    (project.scale_max - project.scale_min)) *
                    180
                }
                y="58"
                className="fill-muted-foreground"
                fontSize="8"
                textAnchor="middle"
              >
                {upperNum}
              </text>
            </svg>
          </div>
        )}

        <div className="flex flex-col gap-2">
          <div className="flex gap-3">
            <SubmitButton
              type="button"
              onClick={onSave}
              disabled={!lower || !peak || !upper || !position.trim() || !hasChanges}
              isLoading={isSaving}
              className="flex-1"
              aria-describedby={
                !position.trim() || (!lower || !peak || !upper) || !hasChanges
                  ? "opinion-hint" : undefined
              }
            >
              {myOpinion ? t("detail.updateOpinion") : t("detail.saveOpinion")}
            </SubmitButton>
          </div>
          {!position.trim() ? (
            <p id="opinion-hint" className="text-xs text-muted-foreground">
              {t("detail.hintPositionRequired")}
            </p>
          ) : !lower || !peak || !upper ? (
            <p id="opinion-hint" className="text-xs text-muted-foreground">
              {t("detail.hintFieldsRequired")}
            </p>
          ) : !hasChanges ? (
            <p id="opinion-hint" className="text-xs text-muted-foreground">
              {t("detail.hintNoChanges")}
            </p>
          ) : null}
        </div>

        {myOpinion && (
          <button
            type="button"
            onClick={onDelete}
            className="text-sm text-destructive hover:underline"
          >
            {t("detail.deleteOpinion")}
          </button>
        )}
      </CardContent>
    </Card>
  );
};

const OtherOpinionsTable = ({
  opinions,
  members,
  currentUserId,
}: {
  opinions: Opinion[];
  members: Member[];
  currentUserId?: string;
}) => {
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

interface ResultsSectionProps {
  result: CalculationResult | null;
  project: ProjectWithRole;
  showIndividual: boolean;
  setShowIndividual: (v: boolean) => void;
  opinions: Opinion[];
}

const ResultsSection = ({
  result,
  project,
  showIndividual,
  setShowIndividual,
  opinions,
}: ResultsSectionProps) => {
  const { t } = useTranslation("projects");
  const { t: tFuzzy } = useTranslation();

  if (!result || opinions.length === 0) {
    return (
      <Card>
        <CardContent className="py-16 text-center">
          <p className="text-muted-foreground">
            {t("detail.noResults")}
          </p>
        </CardContent>
      </Card>
    );
  }

  const scaleRange = project.scale_max - project.scale_min;
  const errorPercent = (result.max_error / scaleRange) * 100;

  const agreementLevel = errorPercent <= 20 ? "high" : errorPercent <= 40 ? "moderate" : "low";
  const agreementColorClass = {
    high: "[&>div]:bg-green-700",
    moderate: "[&>div]:bg-amber-500",
    low: "[&>div]:bg-red-700",
  }[agreementLevel];

  return (
    <div className="space-y-6">
      {/* Best Compromise */}
      <Card className="border-2 border-primary">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {t("detail.bestCompromise")}
            <span className="text-sm font-normal text-muted-foreground">
              (ΓΩMean)
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 text-center mb-4">
            <div>
              <div className="text-xs text-muted-foreground uppercase">{tFuzzy("fuzzy.lower")}</div>
              <div className="font-mono text-2xl font-medium">
                {result.best_compromise.lower.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground uppercase">{tFuzzy("fuzzy.peak")}</div>
              <div className="font-mono text-2xl font-medium">
                {result.best_compromise.peak.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground uppercase">{tFuzzy("fuzzy.upper")}</div>
              <div className="font-mono text-2xl font-medium">
                {result.best_compromise.upper.toFixed(2)}
              </div>
            </div>
          </div>
          <div className="text-center border-t pt-4">
            <div className="text-xs text-muted-foreground uppercase">{tFuzzy("fuzzy.centroid")}</div>
            <div className="font-mono text-3xl font-medium">
              {result.best_compromise.centroid.toFixed(2)}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Arithmetic Mean & Median */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t("detail.arithmeticMean")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="font-mono text-sm">
              {result.arithmetic_mean.lower.toFixed(2)} |{" "}
              {result.arithmetic_mean.peak.toFixed(2)} |{" "}
              {result.arithmetic_mean.upper.toFixed(2)}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {tFuzzy("fuzzy.centroid")}: {result.arithmetic_mean.centroid.toFixed(2)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t("detail.median")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="font-mono text-sm">
              {result.median.lower.toFixed(2)} | {result.median.peak.toFixed(2)} |{" "}
              {result.median.upper.toFixed(2)}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {tFuzzy("fuzzy.centroid")}: {result.median.centroid.toFixed(2)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Max Error & Experts */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm">{t("detail.maxError")}</span>
            <div className="flex items-center gap-2">
              <Badge
                className={cn(
                  "text-xs",
                  agreementLevel === "high" && "bg-green-700 text-white hover:bg-green-800",
                  agreementLevel === "moderate" && "bg-amber-200 text-amber-900 hover:bg-amber-300",
                  agreementLevel === "low" && "bg-red-700 text-white hover:bg-red-800",
                )}
              >
                {t(`detail.agreement.${agreementLevel}`)}
              </Badge>
              <span className="font-mono font-medium">
                {result.max_error.toFixed(2)}
              </span>
            </div>
          </div>
          <Progress value={Math.min(errorPercent, 100)} className={cn("h-2", agreementColorClass)} />
          <div className="flex justify-between items-center mt-4 text-sm text-muted-foreground">
            <span>{t("detail.experts")}</span>
            <span className="font-mono">{result.num_experts}</span>
          </div>
        </CardContent>
      </Card>

      {/* Visualization */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t("detail.visualization")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="triangle" className="space-y-4">
            <TabsList className="w-full">
              <TabsTrigger value="triangle" className="flex-1">
                {t("detail.vizTab.triangle")}
              </TabsTrigger>
              <TabsTrigger value="centroid" className="flex-1">
                {t("detail.vizTab.centroid")}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="triangle">
              <TriangleVisualization
                result={result}
                project={project}
                showIndividual={showIndividual}
                opinions={opinions}
              />
              <div className="flex items-center justify-between mt-4">
                <div className="flex gap-4 text-xs">
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-0.5 bg-blue-500" />
                    <span>{tFuzzy("fuzzy.mean")}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-0.5 bg-green-500" />
                    <span>{tFuzzy("fuzzy.median")}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-0.5 bg-foreground" />
                    <span>{tFuzzy("fuzzy.best")}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="showIndividual"
                    checked={showIndividual}
                    onCheckedChange={(checked) => setShowIndividual(!!checked)}
                  />
                  <Label htmlFor="showIndividual" className="text-xs cursor-pointer">
                    {t("detail.showIndividual")}
                  </Label>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="centroid">
              <CentroidBarChart opinions={opinions} result={result} />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
};

interface TriangleVisualizationProps {
  result: CalculationResult;
  project: ProjectWithRole;
  showIndividual: boolean;
  opinions: Opinion[];
}

const TriangleVisualization = ({
  result,
  project,
  showIndividual,
  opinions,
}: TriangleVisualizationProps) => {
  const { t: tCommon } = useTranslation();
  const scaleToX = (value: number) => {
    return (
      40 +
      ((value - project.scale_min) / (project.scale_max - project.scale_min)) * 320
    );
  };

  const baseY = 160;
  const peakY = 30;

  return (
    <svg viewBox="0 0 400 200" className="w-full" role="img" aria-label={tCommon("a11y.resultsChartDesc")}>
      {/* Axes */}
      <line
        x1="40"
        y1={baseY}
        x2="360"
        y2={baseY}
        stroke="currentColor"
        strokeOpacity="0.2"
      />
      <line
        x1="40"
        y1={baseY}
        x2="40"
        y2="20"
        stroke="currentColor"
        strokeOpacity="0.2"
      />

      {/* Scale labels */}
      <text
        x="40"
        y={baseY + 15}
        className="fill-muted-foreground"
        fontSize="10"
        textAnchor="middle"
      >
        {project.scale_min}
      </text>
      <text
        x="360"
        y={baseY + 15}
        className="fill-muted-foreground"
        fontSize="10"
        textAnchor="middle"
      >
        {project.scale_max}
      </text>

      {/* Individual opinions */}
      {showIndividual &&
        opinions.map((op, i) => (
          <polygon
            key={op.id}
            points={`${scaleToX(op.lower_bound)},${baseY} ${scaleToX(op.peak)},${peakY + 20} ${scaleToX(op.upper_bound)},${baseY}`}
            fill="currentColor"
            fillOpacity="0.05"
            stroke="currentColor"
            strokeOpacity="0.15"
            strokeWidth="1"
          />
        ))}

      {/* Arithmetic Mean - Blue */}
      <polygon
        points={`${scaleToX(result.arithmetic_mean.lower)},${baseY} ${scaleToX(result.arithmetic_mean.peak)},${peakY + 10} ${scaleToX(result.arithmetic_mean.upper)},${baseY}`}
        fill="rgb(59, 130, 246)"
        fillOpacity="0.1"
        stroke="rgb(59, 130, 246)"
        strokeWidth="1.5"
        strokeDasharray="4,4"
      />

      {/* Median - Green */}
      <polygon
        points={`${scaleToX(result.median.lower)},${baseY} ${scaleToX(result.median.peak)},${peakY + 10} ${scaleToX(result.median.upper)},${baseY}`}
        fill="rgb(34, 197, 94)"
        fillOpacity="0.1"
        stroke="rgb(34, 197, 94)"
        strokeWidth="1.5"
        strokeDasharray="4,4"
      />

      {/* Best Compromise - Black/White (theme-aware) */}
      <polygon
        points={`${scaleToX(result.best_compromise.lower)},${baseY} ${scaleToX(result.best_compromise.peak)},${peakY} ${scaleToX(result.best_compromise.upper)},${baseY}`}
        fill="currentColor"
        fillOpacity="0.1"
        stroke="currentColor"
        strokeWidth="2"
      />

      {/* Centroid marker */}
      <line
        x1={scaleToX(result.best_compromise.centroid)}
        y1={baseY}
        x2={scaleToX(result.best_compromise.centroid)}
        y2={baseY - 40}
        stroke="currentColor"
        strokeWidth="1"
        strokeDasharray="2,2"
      />
      <circle
        cx={scaleToX(result.best_compromise.centroid)}
        cy={baseY - 45}
        r="3"
        fill="currentColor"
      />
    </svg>
  );
};

interface TeamTableProps {
  members: Member[];
  pendingInvitations: ProjectInvitation[];
  isAdmin: boolean;
  currentUserId?: string;
  selectedMemberId?: string;
  onRemove: (userId: string) => void;
  onMemberClick: (member: Member) => void;
}

const TeamTable = ({
  members,
  pendingInvitations,
  isAdmin,
  currentUserId,
  selectedMemberId,
  onRemove,
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

interface MemberProfileDialogProps {
  member: Member | null;
  opinion: Opinion | null;
  onOpenChange: (open: boolean) => void;
}

const MemberProfileDialog = ({
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
          <DialogDescription className="flex flex-col items-center gap-1">
            <Badge
              variant={member.role === "admin" ? "default" : "secondary"}
            >
              {t(`roles.${member.role}`)}
            </Badge>
            <span className="sr-only">{t("memberProfile.dialogDescription")}</span>
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

export default ProjectDetail;
