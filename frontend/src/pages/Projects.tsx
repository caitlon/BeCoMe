import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { Plus, Users, Key, MoreHorizontal, Loader2, Mail, Inbox } from "lucide-react";
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
import { Navbar } from "@/components/layout/Navbar";
import { CreateProjectModal } from "@/components/modals/CreateProjectModal";
import { InviteExpertModal } from "@/components/modals/InviteExpertModal";
import { DeleteConfirmModal } from "@/components/modals/DeleteConfirmModal";
import { api } from "@/lib/api";
import { ProjectWithRole, Invitation } from "@/types/api";
import { useToast } from "@/hooks/use-toast";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

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
    transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] },
  },
};

const Projects = () => {
  const { t } = useTranslation("projects");
  const { t: tCommon } = useTranslation();
  const { toast } = useToast();
  useDocumentTitle(tCommon("pageTitle.projects"));
  const [projects, setProjects] = useState<ProjectWithRole[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [selectedProject, setSelectedProject] = useState<ProjectWithRole | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [projectsData, invitationsData] = await Promise.all([
        api.getProjects(),
        api.getInvitations(),
      ]);
      setProjects(projectsData);
      setInvitations(invitationsData);
    } catch (error) {
      toast({
        title: t("toast.error"),
        description: t("toast.loadFailed"),
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  }, [toast, t]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleAcceptInvitation = async (invitationId: string) => {
    try {
      await api.acceptInvitation(invitationId);
      toast({ title: t("toast.invitationAccepted") });
      fetchData();
    } catch (error) {
      toast({
        title: t("toast.error"),
        description: error instanceof Error ? error.message : t("toast.acceptFailed"),
        variant: "destructive",
      });
    }
  };

  const handleDeclineInvitation = async (invitationId: string) => {
    try {
      await api.declineInvitation(invitationId);
      toast({ title: t("toast.invitationDeclined") });
      fetchData();
    } catch (error) {
      toast({
        title: t("toast.error"),
        description: error instanceof Error ? error.message : t("toast.declineFailed"),
        variant: "destructive",
      });
    }
  };

  const handleDeleteProject = async () => {
    if (!selectedProject) return;
    try {
      await api.deleteProject(selectedProject.id);
      toast({ title: t("toast.projectDeleted") });
      setDeleteModalOpen(false);
      setSelectedProject(null);
      fetchData();
    } catch (error) {
      toast({
        title: t("toast.error"),
        description: error instanceof Error ? error.message : t("toast.deleteFailed"),
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

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      
      <main id="main-content" className="container mx-auto px-6 pt-24 pb-16">
        <h1 className="sr-only">{t("heading")}</h1>
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
                <h3 className="font-medium text-lg mb-2">{t("empty.title")}</h3>
                <p className="text-muted-foreground mb-6">
                  {t("empty.description")}
                </p>
                <Button onClick={() => setCreateModalOpen(true)} className="gap-2">
                  <Plus className="h-4 w-4" />
                  {t("empty.createFirst")}
                </Button>
              </motion.div>
            ) : (
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
                              <Button variant="ghost" size="icon" className="h-8 w-8 relative z-10">
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
                <h3 className="font-medium text-lg mb-2">{t("invitations.empty.title")}</h3>
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
                            <h3 className="font-medium text-lg mb-1">
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
                                {t("invitations.invitedDate")}: {new Date(invitation.invited_at).toLocaleDateString()}
                              </span>
                            </div>

                            <div className="flex gap-3">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleDeclineInvitation(invitation.id)}
                              >
                                {t("buttons.decline")}
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => handleAcceptInvitation(invitation.id)}
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
      </main>

      <CreateProjectModal
        open={createModalOpen}
        onOpenChange={setCreateModalOpen}
        onSuccess={fetchData}
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
    </div>
  );
};

export default Projects;
