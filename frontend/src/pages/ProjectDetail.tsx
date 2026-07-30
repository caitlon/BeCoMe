import { useState, useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Loader2,
  Users,
  UserPlus,
  Trash2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Navbar } from "@/components/layout/Navbar";
import { InviteExpertModal } from "@/components/modals/InviteExpertModal";
import { DeleteConfirmModal } from "@/components/modals/DeleteConfirmModal";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import {
  OpinionForm,
  OpinionFormOutput,
  OtherOpinionsTable,
  ResultsSection,
  ResultExportMenu,
  TeamTable,
  MemberProfileDialog,
  useOpinionForm,
} from "@/components/project";
import { api, HttpError } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import { Member, ProjectInvitation } from "@/types/api";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useMediaQuery } from "@/hooks/use-media-query";

const ProjectDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { toast } = useToast();
  const { t } = useTranslation("projects");
  const { t: tCommon } = useTranslation();

  const queryClient = useQueryClient();

  // Render one layout for the active breakpoint (lg = 1024px) instead of
  // mounting the desktop grid and the mobile tabs together and toggling CSS
  // visibility: a dual mount duplicates the opinion form, so a hidden copy
  // would own the input refs and steal error focus on submit.
  const isDesktop = useMediaQuery("(min-width: 1024px)");

  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [teamOpen, setTeamOpen] = useState(true);
  const [showIndividual, setShowIndividual] = useState(false);
  const [profileMember, setProfileMember] = useState<Member | null>(null);

  const [transferTarget, setTransferTarget] = useState<Member | null>(null);

  /* v8 ignore next -- defensive fallback: id always provided by route params */
  const projectId = id ?? "";

  const projectQuery = useQuery({
    queryKey: queryKeys.project(projectId),
    queryFn: () => api.getProject(projectId),
    enabled: !!id,
  });
  const opinionsQuery = useQuery({
    queryKey: queryKeys.projectOpinions(projectId),
    queryFn: () => api.getOpinions(projectId),
    enabled: !!id,
  });
  const resultQuery = useQuery({
    queryKey: queryKeys.projectResult(projectId),
    queryFn: () => api.getResult(projectId),
    enabled: !!id,
  });
  const membersQuery = useQuery({
    queryKey: queryKeys.projectMembers(projectId),
    queryFn: () => api.getMembers(projectId),
    enabled: !!id,
  });
  const invitationsQuery = useQuery({
    queryKey: queryKeys.projectInvitations(projectId),
    queryFn: () =>
      api.getProjectInvitations(projectId).catch((error: unknown) => {
        // Experts may not list invitations; treat forbidden as "none".
        if (error instanceof HttpError && error.status === 403) {
          return [] as ProjectInvitation[];
        }
        throw error;
      }),
    enabled: !!id,
  });

  const project = projectQuery.data ?? null;
  const opinions = opinionsQuery.data ?? [];
  const result = resultQuery.data ?? null;
  const members = membersQuery.data ?? [];
  const pendingInvitations = invitationsQuery.data ?? [];
  const isLoading =
    projectQuery.isPending ||
    opinionsQuery.isPending ||
    resultQuery.isPending ||
    membersQuery.isPending ||
    invitationsQuery.isPending;
  // isLoadingError only: a failed background refetch keeps cached data on
  // screen and must not eject the user from the page.
  const hasLoadError =
    projectQuery.isLoadingError ||
    opinionsQuery.isLoadingError ||
    resultQuery.isLoadingError ||
    membersQuery.isLoadingError ||
    invitationsQuery.isLoadingError;

  useDocumentTitle(project ? tCommon("pageTitle.projectDetail", { name: project.name }) : tCommon("common.loading"));

  useEffect(() => {
    if (hasLoadError) {
      toast({
        title: t("toast.error"),
        description: t("toast.loadProjectFailed"),
        variant: "destructive",
      });
      navigate("/projects");
    }
  }, [hasLoadError, toast, navigate, t]);

  const myOpinion = opinions.find((o) => o.user_id === user?.id);
  const opinionForm = useOpinionForm(project, myOpinion);
  const otherOpinions = opinions.filter((o) => o.user_id !== user?.id);
  const isAdmin = project?.role === "admin";
  const profileOpinion = profileMember
    ? opinions.find((o) => o.user_id === profileMember.user_id) ?? null
    : null;

  const invalidateProject = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId) });

  const saveOpinion = useMutation({
    mutationFn: (values: OpinionFormOutput) =>
      api.createOrUpdateOpinion(projectId, {
        position: values.position,
        lower_bound: values.lower,
        peak: values.peak,
        upper_bound: values.upper,
      }),
    onSuccess: () => {
      toast({ title: t("toast.opinionSaved") });
      invalidateProject();
    },
    onError: (error) => {
      toast({
        title: t("toast.error"),
        description: error instanceof Error ? error.message : t("toast.saveFailed"),
        variant: "destructive",
      });
    },
  });

  const handleSaveOpinion = async (values: OpinionFormOutput) => {
    await saveOpinion.mutateAsync(values).catch(() => {
      // errors are surfaced via the mutation's onError toast
    });
  };

  const handleDeleteOpinion = async () => {
    try {
      await api.deleteOpinion(projectId);
      toast({ title: t("toast.opinionDeleted") });
      invalidateProject();
    } catch {
      toast({
        title: t("toast.error"),
        description: t("toast.deleteOpinionFailed"),
        variant: "destructive",
      });
    }
  };

  const handleDeleteProject = async () => {
    try {
      await api.deleteProject(projectId);
      toast({ title: t("toast.projectDeleted") });
      queryClient.removeQueries({ queryKey: queryKeys.project(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.projects, exact: true });
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
    try {
      await api.removeMember(projectId, userId);
      toast({ title: t("toast.memberRemoved") });
      invalidateProject();
    } catch {
      toast({
        title: t("toast.error"),
        description: t("toast.removeMemberFailed"),
        variant: "destructive",
      });
    }
  };

  const handleTransferOwnership = async () => {
    /* v8 ignore next -- defensive guard: target is always set when invoked */
    if (!transferTarget) return;
    try {
      await api.transferOwnership(projectId, transferTarget.user_id);
      toast({ title: t("toast.ownershipTransferred") });
      setTransferTarget(null);
      invalidateProject();
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

  const resultsErrorFallback = (
    <Card>
      <CardContent className="py-16 text-center">
        <p className="text-muted-foreground">{t("detail.resultsError")}</p>
      </CardContent>
    </Card>
  );

  // Single instances shared between the desktop grid and the mobile tabs. Only
  // one layout mounts at a time, so each block renders exactly once.
  const opinionsColumn = (
    <div className="space-y-6">
      <OpinionForm
        form={opinionForm}
        project={project}
        myOpinion={myOpinion}
        isSaving={saveOpinion.isPending}
        onSubmit={handleSaveOpinion}
        onDelete={handleDeleteOpinion}
      />
      <OtherOpinionsTable opinions={otherOpinions} members={members} currentUserId={user?.id} />
    </div>
  );

  const resultsColumn = (
    <ErrorBoundary fallback={resultsErrorFallback}>
      <ResultsSection
        result={result}
        project={project}
        showIndividual={showIndividual}
        setShowIndividual={setShowIndividual}
        opinions={opinions}
      />
    </ErrorBoundary>
  );

  const teamTable = (
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
  );

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
          <h1 className="font-display text-3xl md:text-4xl font-normal mb-2">
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
            {result && opinions.length > 0 && (
              <div className="ml-auto">
                <ResultExportMenu project={project} />
              </div>
            )}
          </div>
        </motion.div>

        {isDesktop ? (
          <>
            {/* Main Content - Two Columns on Desktop */}
            <div className="grid grid-cols-2 gap-8">
              {/* Left Column - Opinions */}
              {opinionsColumn}

              {/* Right Column - Results */}
              <div className="space-y-6">{resultsColumn}</div>
            </div>

            {/* Team Section - Desktop Collapsible */}
            <div className="mt-8">
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
                <CollapsibleContent>{teamTable}</CollapsibleContent>
              </Collapsible>
            </div>
          </>
        ) : (
          /* Mobile - Tabs */
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

            <TabsContent value="opinions">{opinionsColumn}</TabsContent>

            <TabsContent value="results">{resultsColumn}</TabsContent>

            <TabsContent value="team">{teamTable}</TabsContent>
          </Tabs>
        )}
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
