import { useState } from "react";
import { Link } from "react-router";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Users, Key, MoreHorizontal, Loader2, Mail, Inbox, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { CreateProjectModal } from "@/components/modals/CreateProjectModal";
import { InviteExpertModal } from "@/components/modals/InviteExpertModal";
import { DeleteConfirmModal } from "@/components/modals/DeleteConfirmModal";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/queryKeys";
import { ProjectWithRole } from "@/types/api";
import { isUnauthorized } from "@/lib/errors";
import { useToast } from "@/hooks/use-toast";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { formatDate } from "@/lib/formatDate";

// Multiple of the 1/2/3-column grid so every full page fills whole rows.
const PAGE_SIZE = 24;

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.1 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] as const },
  },
};

const Projects = () => {
  const { t, i18n } = useTranslation("projects");
  const { t: tCommon } = useTranslation();
  const { toast } = useToast();
  useDocumentTitle(tCommon("pageTitle.projects"));
  const queryClient = useQueryClient();
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [selectedProject, setSelectedProject] = useState<ProjectWithRole | null>(null);

  const projectsQuery = useInfiniteQuery({
    queryKey: queryKeys.projects,
    queryFn: ({ pageParam }) => api.getProjects({ limit: PAGE_SIZE, offset: pageParam }),
    initialPageParam: 0,
    // The list endpoint returns no total count: a full page means there may
    // be more, a short page means the end was reached.
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length === PAGE_SIZE ? allPages.flat().length : undefined,
  });
  const invitationsQuery = useQuery({
    queryKey: queryKeys.invitations,
    queryFn: () => api.getInvitations(),
  });

  const projects = projectsQuery.data?.pages.flat() ?? [];
  const invitations = invitationsQuery.data ?? [];
  const isLoading = projectsQuery.isPending || invitationsQuery.isPending;
  // isLoadingError only: a failed background refetch keeps cached data on
  // screen and should not replace it with the inline error state.
  const hasLoadError = projectsQuery.isLoadingError || invitationsQuery.isLoadingError;

  const invalidateLists = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.projects });
    queryClient.invalidateQueries({ queryKey: queryKeys.invitations });
  };

  const acceptInvitation = useMutation({
    mutationFn: (invitationId: string) => api.acceptInvitation(invitationId),
    onSuccess: () => {
      toast({ title: t("toast.invitationAccepted") });
      invalidateLists();
    },
    onError: (error) => {
      // A 401 here already triggered the silent-refresh/session-expired flow in
      // the ApiClient; that toast is the single source of truth, so skip this one.
      if (isUnauthorized(error)) return;
      toast({
        title: t("toast.error"),
        description: error instanceof Error ? error.message : t("toast.acceptFailed"),
        variant: "destructive",
      });
    },
  });

  const declineInvitation = useMutation({
    mutationFn: (invitationId: string) => api.declineInvitation(invitationId),
    onSuccess: () => {
      toast({ title: t("toast.invitationDeclined") });
      invalidateLists();
    },
    onError: (error) => {
      if (isUnauthorized(error)) return;
      toast({
        title: t("toast.error"),
        description: error instanceof Error ? error.message : t("toast.declineFailed"),
        variant: "destructive",
      });
    },
  });

  const deleteProject = useMutation({
    mutationFn: (projectId: string) => api.deleteProject(projectId),
    onSuccess: () => {
      toast({ title: t("toast.projectDeleted") });
      setDeleteModalOpen(false);
      setSelectedProject(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.projects });
    },
    onError: (error) => {
      if (isUnauthorized(error)) return;
      toast({
        title: t("toast.error"),
        description: error instanceof Error ? error.message : t("toast.deleteFailed"),
        variant: "destructive",
      });
    },
  });

  const handleDeleteProject = async () => {
    /* v8 ignore next */
    if (!selectedProject) return;
    await deleteProject.mutateAsync(selectedProject.id).catch(() => {
      // errors are surfaced via the mutation's onError toast
    });
  };

  if (isLoading) {
    return (
      <PageShell variant="centered">
        <output aria-label={tCommon("a11y.loading")}>
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <span className="sr-only">{tCommon("common.loading")}</span>
        </output>
      </PageShell>
    );
  }

  if (hasLoadError) {
    return (
      <PageShell variant="centered">
        <div role="alert" className="flex flex-col items-center gap-4 p-6 text-center">
          <AlertTriangle className="h-8 w-8 text-muted-foreground" />
          <h1 className="font-display font-medium text-lg">{t("error.title")}</h1>
          <p className="text-muted-foreground max-w-sm">{t("error.description")}</p>
          <Button
            onClick={() => {
              projectsQuery.refetch();
              invitationsQuery.refetch();
            }}
          >
            {tCommon("errors.retry")}
          </Button>
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell>
        <PageHeader title={t("heading")} />
        <Tabs defaultValue="projects" className="space-y-6">
          <div className="flex items-center justify-between">
            <TabsList>
              <TabsTrigger value="projects">{t("tabs.myProjects")}</TabsTrigger>
              <TabsTrigger value="invitations" className="gap-2">
                {t("tabs.invitations")}
                {invitations.length > 0 && (
                  <Badge variant="secondary" className="ml-1 h-5 px-1.5">
                    {invitations.length}
                  </Badge>
                )}
              </TabsTrigger>
            </TabsList>

            <Button onClick={() => setCreateModalOpen(true)} className="gap-2">
              <Plus className="h-4 w-4" />
              {t("buttons.newProject")}
            </Button>
          </div>

          <TabsContent value="projects" className="space-y-6">
            {projects.length === 0 ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-center py-16"
              >
                <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
                  <Inbox className="h-8 w-8 text-muted-foreground" />
                </div>
                <h3 className="font-display font-medium text-lg mb-2">{t("empty.title")}</h3>
                <p className="text-muted-foreground mb-6">
                  {t("empty.description")}
                </p>
                <Button onClick={() => setCreateModalOpen(true)} className="gap-2">
                  <Plus className="h-4 w-4" />
                  {t("empty.createFirst")}
                </Button>
              </motion.div>
            ) : (
              <>
              <motion.div
                className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
                variants={containerVariants}
                initial="hidden"
                animate="visible"
              >
                {projects.map((project) => (
                  <motion.div
                    key={project.id}
                    variants={itemVariants}
                    whileHover={{ y: -4, transition: { duration: 0.2 } }}
                  >
                    <Card className="relative h-full hover:shadow-lg transition-shadow duration-300 cursor-pointer">
                      <CardContent className="p-6">
                        <div className="flex items-start justify-between mb-3">
                          <Link
                            to={`/projects/${project.id}`}
                            className="font-medium text-lg hover:underline line-clamp-1 after:absolute after:inset-0 after:content-['']"
                          >
                            {project.name}
                          </Link>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon" className="h-8 w-8 relative z-10" aria-label={t("dropdown.openMenu")}>
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem asChild>
                                <Link to={`/projects/${project.id}`}>
                                  {t("dropdown.viewProject")}
                                </Link>
                              </DropdownMenuItem>
                              {project.role === 'admin' && (
                                <>
                                  <DropdownMenuItem
                                    onClick={() => {
                                      setSelectedProject(project);
                                      setInviteModalOpen(true);
                                    }}
                                  >
                                    {t("dropdown.inviteExpert")}
                                  </DropdownMenuItem>
                                  <DropdownMenuSeparator />
                                  <DropdownMenuItem
                                    onClick={() => {
                                      setSelectedProject(project);
                                      setDeleteModalOpen(true);
                                    }}
                                    className="text-destructive"
                                  >
                                    {t("dropdown.deleteProject")}
                                  </DropdownMenuItem>
                                </>
                              )}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                        
                        <p className="text-sm text-muted-foreground mb-4 line-clamp-2 min-h-[2.5rem]">
                          {project.description || t("card.noDescription")}
                        </p>

                        <div className="text-xs text-muted-foreground mb-4 font-mono bg-muted px-2 py-1 rounded">
                          {t("card.scale")}: {project.scale_min} — {project.scale_max} {project.scale_unit}
                        </div>

                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Users className="h-4 w-4" />
                            <span>{project.member_count} {t("card.experts")}</span>
                          </div>
                          <Badge variant={project.role === 'admin' ? 'default' : 'secondary'}>
                            {project.role === 'admin' ? (
                              <><Key className="h-3 w-3 mr-1" /> {t("roles.admin")}</>
                            ) : (
                              t("roles.expert")
                            )}
                          </Badge>
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                ))}
              </motion.div>
              {projectsQuery.hasNextPage && (
                <div className="flex justify-center pt-2">
                  <Button
                    variant="outline"
                    onClick={() => projectsQuery.fetchNextPage()}
                    disabled={projectsQuery.isFetchingNextPage}
                    className="gap-2"
                  >
                    {projectsQuery.isFetchingNextPage && (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    )}
                    {t("buttons.loadMore")}
                  </Button>
                </div>
              )}
              </>
            )}
          </TabsContent>

          <TabsContent value="invitations" className="space-y-6">
            {invitations.length === 0 ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-center py-16"
              >
                <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
                  <Mail className="h-8 w-8 text-muted-foreground" />
                </div>
                <h3 className="font-display font-medium text-lg mb-2">{t("invitations.empty.title")}</h3>
                <p className="text-muted-foreground">
                  {t("invitations.empty.description")}
                </p>
              </motion.div>
            ) : (
              <motion.div
                className="space-y-4 max-w-2xl"
                variants={containerVariants}
                initial="hidden"
                animate="visible"
              >
                <p className="text-muted-foreground">
                  {t("invitations.pending", { count: invitations.length })}
                </p>

                {invitations.map((invitation) => (
                  <motion.div key={invitation.id} variants={itemVariants}>
                    <Card>
                      <CardContent className="p-6">
                        <div className="flex items-start gap-4">
                          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                            <Mail className="h-5 w-5" />
                          </div>
                          
                          <div className="flex-1 min-w-0">
                            <h3 className="font-display font-medium text-lg mb-1">
                              {invitation.project_name}
                            </h3>

                            <p className="text-sm text-muted-foreground mb-3">
                              {t("invitations.invitedBy")}: {invitation.inviter_first_name} ({invitation.inviter_email})
                            </p>

                            {invitation.project_description && (
                              <p className="text-sm text-muted-foreground mb-3 italic">
                                "{invitation.project_description}"
                              </p>
                            )}

                            <div className="flex flex-wrap gap-4 text-xs text-muted-foreground mb-4">
                              <span className="font-mono bg-muted px-2 py-1 rounded">
                                {t("card.scale")}: {invitation.project_scale_min} — {invitation.project_scale_max} {invitation.project_scale_unit}
                              </span>
                              <span className="flex items-center gap-1">
                                <Users className="h-3 w-3" />
                                {invitation.current_experts_count} {t("card.experts")}
                              </span>
                              <span>
                                {t("invitations.invitedDate")}: {formatDate(invitation.invited_at, i18n.language)}
                              </span>
                            </div>

                            <div className="flex gap-3">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => declineInvitation.mutate(invitation.id)}
                              >
                                {t("buttons.decline")}
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => acceptInvitation.mutate(invitation.id)}
                              >
                                {t("buttons.accept")}
                              </Button>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                ))}
              </motion.div>
            )}
          </TabsContent>
        </Tabs>

      <CreateProjectModal
        open={createModalOpen}
        onOpenChange={setCreateModalOpen}
        onSuccess={() => queryClient.invalidateQueries({ queryKey: queryKeys.projects })}
      />

      <InviteExpertModal
        open={inviteModalOpen}
        onOpenChange={setInviteModalOpen}
        projectId={selectedProject?.id}
        projectName={selectedProject?.name}
      />

      <DeleteConfirmModal
        open={deleteModalOpen}
        onOpenChange={setDeleteModalOpen}
        title={t("deleteModal.title")}
        description={t("deleteModal.description", { name: selectedProject?.name })}
        details={[
          t("deleteModal.details.opinions"),
          t("deleteModal.details.results"),
          t("deleteModal.details.invitations")
        ]}
        onConfirm={handleDeleteProject}
        confirmText={t("deleteModal.confirm")}
        loadingText={t("deleteModal.deleting")}
      />
    </PageShell>
  );
};

export default Projects;
