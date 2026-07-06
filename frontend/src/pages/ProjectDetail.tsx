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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Navbar } from "@/components/layout/Navbar";
import { InviteExpertModal } from "@/components/modals/InviteExpertModal";
import { DeleteConfirmModal } from "@/components/modals/DeleteConfirmModal";
import {
  OpinionForm,
  OtherOpinionsTable,
  ResultsSection,
  TeamTable,
  MemberProfileDialog,
} from "@/components/project";
import { api, HttpError } from "@/lib/api";
import { ProjectWithRole, Opinion, CalculationResult, Member, ProjectInvitation } from "@/types/api";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

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
  const [transferTarget, setTransferTarget] = useState<Member | null>(null);
  useDocumentTitle(project ? tCommon("pageTitle.projectDetail", { name: project.name }) : tCommon("common.loading"));

  const myOpinion = opinions.find((o) => o.user_id === user?.id);
  const otherOpinions = opinions.filter((o) => o.user_id !== user?.id);
  const isAdmin = project?.role === "admin";
  const profileOpinion = profileMember
    ? opinions.find((o) => o.user_id === profileMember.user_id) ?? null
    : null;

  const fetchData = useCallback(async () => {
    /* v8 ignore next -- defensive guard: id always provided by route params */
    if (!id) return;
    try {
      const [projectData, opinionsData, resultData, membersData, invitationsData] =
        await Promise.all([
          api.getProject(id),
          api.getOpinions(id),
          api.getResult(id),
          api.getMembers(id),
          api.getProjectInvitations(id).catch((error: unknown) => {
            if (error instanceof HttpError && error.status === 403) {
              return [] as ProjectInvitation[];
            }
            throw error;
          }),
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
    } catch {
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
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data load on mount
    fetchData();
  }, [fetchData]);

  const handleSaveOpinion = async () => {
    /* v8 ignore next -- defensive guard: id and project always present when form is shown */
    if (!id || !project) return;

    const lowerNum = Number.parseFloat(lower);
    const peakNum = Number.parseFloat(peak);
    const upperNum = Number.parseFloat(upper);

    // Validation
    /* v8 ignore next 7 -- defensive guard: button is disabled when fields are empty */
    if (Number.isNaN(lowerNum) || Number.isNaN(peakNum) || Number.isNaN(upperNum)) {
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
    /* v8 ignore next -- defensive guard: id always provided by route params */
    if (!id) return;
    try {
      await api.deleteOpinion(id);
      setPosition("");
      setLower("");
      setPeak("");
      setUpper("");
      toast({ title: t("toast.opinionDeleted") });
      fetchData();
    } catch {
      toast({
        title: t("toast.error"),
        description: t("toast.deleteOpinionFailed"),
        variant: "destructive",
      });
    }
  };

  const handleDeleteProject = async () => {
    /* v8 ignore next -- defensive guard: id always provided by route params */
    if (!id) return;
    try {
      await api.deleteProject(id);
      toast({ title: t("toast.projectDeleted") });
      navigate("/projects");
    } catch {
      toast({
        title: t("toast.error"),
        description: t("toast.deleteFailed"),
        variant: "destructive",
      });
    }
  };

  const handleRemoveMember = async (userId: string) => {
    /* v8 ignore next -- defensive guard: id always provided by route params */
    if (!id) return;
    try {
      await api.removeMember(id, userId);
      toast({ title: t("toast.memberRemoved") });
      fetchData();
    } catch {
      toast({
        title: t("toast.error"),
        description: t("toast.removeMemberFailed"),
        variant: "destructive",
      });
    }
  };

  const handleTransferOwnership = async () => {
    /* v8 ignore next -- defensive guard: id and target are always set when invoked */
    if (!id || !transferTarget) return;
    try {
      await api.transferOwnership(id, transferTarget.user_id);
      toast({ title: t("toast.ownershipTransferred") });
      setTransferTarget(null);
      fetchData();
    } catch {
      toast({
        title: t("toast.error"),
        description: t("toast.transferOwnershipFailed"),
        variant: "destructive",
      });
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen">
        <Navbar />
        <main id="main-content" className="pt-24 flex items-center justify-center">
          <output aria-label={tCommon("a11y.loading")}>
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <span className="sr-only">{tCommon("common.loading")}</span>
          </output>
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
                onTransfer={(member) => setTransferTarget(member)}
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
                onTransfer={(member) => setTransferTarget(member)}
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

      <DeleteConfirmModal
        open={!!transferTarget}
        onOpenChange={(open) => !open && setTransferTarget(null)}
        title={t("transferOwnership.title")}
        description={t("transferOwnership.description", {
          name: transferTarget
            ? `${transferTarget.first_name} ${transferTarget.last_name ?? ""}`.trim()
            : "",
        })}
        onConfirm={handleTransferOwnership}
        confirmText={t("transferOwnership.confirm")}
      />

      <MemberProfileDialog
        member={profileMember}
        opinion={profileOpinion}
        onOpenChange={(open) => !open && setProfileMember(null)}
      />
    </div>
  );
};

export default ProjectDetail;
