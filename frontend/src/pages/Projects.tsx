import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
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

const Projects = () => {
  const { toast } = useToast();
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
        title: "Error",
        description: "Failed to load projects",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleAcceptInvitation = async (invitationId: string) => {
    try {
      await api.acceptInvitation(invitationId);
      toast({ title: "Invitation accepted" });
      fetchData();
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to accept",
        variant: "destructive",
      });
    }
  };

  const handleDeclineInvitation = async (invitationId: string) => {
    try {
      await api.declineInvitation(invitationId);
      toast({ title: "Invitation declined" });
      fetchData();
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to decline",
        variant: "destructive",
      });
    }
  };

  const handleDeleteProject = async () => {
    if (!selectedProject) return;
    try {
      await api.deleteProject(selectedProject.id);
      toast({ title: "Project deleted" });
      setDeleteModalOpen(false);
      setSelectedProject(null);
      fetchData();
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to delete",
        variant: "destructive",
      });
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen">
        <Navbar />
        <div className="pt-24 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      
      <main className="container mx-auto px-6 pt-24 pb-16">
        <Tabs defaultValue="projects" className="space-y-6">
          <div className="flex items-center justify-between">
            <TabsList>
              <TabsTrigger value="projects">My Projects</TabsTrigger>
              <TabsTrigger value="invitations" className="gap-2">
                Invitations
                {invitations.length > 0 && (
                  <Badge variant="secondary" className="ml-1 h-5 px-1.5">
                    {invitations.length}
                  </Badge>
                )}
              </TabsTrigger>
            </TabsList>
            
            <Button onClick={() => setCreateModalOpen(true)} className="gap-2">
              <Plus className="h-4 w-4" />
              New Project
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
                <h3 className="font-medium text-lg mb-2">No projects yet</h3>
                <p className="text-muted-foreground mb-6">
                  Create your first project to start collecting expert opinions.
                </p>
                <Button onClick={() => setCreateModalOpen(true)} className="gap-2">
                  <Plus className="h-4 w-4" />
                  Create Your First Project
                </Button>
              </motion.div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {projects.map((project, index) => (
                  <motion.div
                    key={project.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                  >
                    <Card className="h-full hover:shadow-md transition-shadow">
                      <CardContent className="p-6">
                        <div className="flex items-start justify-between mb-3">
                          <Link 
                            to={`/projects/${project.id}`}
                            className="font-medium text-lg hover:underline line-clamp-1"
                          >
                            {project.name}
                          </Link>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon" className="h-8 w-8">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem asChild>
                                <Link to={`/projects/${project.id}`}>
                                  View Project
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
                                    Invite Expert
                                  </DropdownMenuItem>
                                  <DropdownMenuSeparator />
                                  <DropdownMenuItem 
                                    onClick={() => {
                                      setSelectedProject(project);
                                      setDeleteModalOpen(true);
                                    }}
                                    className="text-destructive"
                                  >
                                    Delete Project
                                  </DropdownMenuItem>
                                </>
                              )}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                        
                        <p className="text-sm text-muted-foreground mb-4 line-clamp-2 min-h-[2.5rem]">
                          {project.description || "No description"}
                        </p>
                        
                        <div className="text-xs text-muted-foreground mb-4 font-mono bg-muted px-2 py-1 rounded">
                          Scale: {project.scale_min} — {project.scale_max} {project.scale_unit}
                        </div>
                        
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Users className="h-4 w-4" />
                            <span>{project.member_count} experts</span>
                          </div>
                          <Badge variant={project.role === 'admin' ? 'default' : 'secondary'}>
                            {project.role === 'admin' ? (
                              <><Key className="h-3 w-3 mr-1" /> Admin</>
                            ) : (
                              'Expert'
                            )}
                          </Badge>
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                ))}
              </div>
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
                <h3 className="font-medium text-lg mb-2">No pending invitations</h3>
                <p className="text-muted-foreground">
                  When someone invites you to a project, it will appear here.
                </p>
              </motion.div>
            ) : (
              <div className="space-y-4 max-w-2xl">
                <p className="text-muted-foreground">
                  You have {invitations.length} pending invitation{invitations.length > 1 ? 's' : ''}
                </p>
                
                {invitations.map((invitation, index) => (
                  <motion.div
                    key={invitation.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                  >
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
                              Invited by: {invitation.inviter_first_name} ({invitation.inviter_email})
                            </p>
                            
                            {invitation.project_description && (
                              <p className="text-sm text-muted-foreground mb-3 italic">
                                "{invitation.project_description}"
                              </p>
                            )}
                            
                            <div className="flex flex-wrap gap-4 text-xs text-muted-foreground mb-4">
                              <span className="font-mono bg-muted px-2 py-1 rounded">
                                Scale: {invitation.project_scale_min} — {invitation.project_scale_max} {invitation.project_scale_unit}
                              </span>
                              <span className="flex items-center gap-1">
                                <Users className="h-3 w-3" />
                                {invitation.current_experts_count} experts
                              </span>
                              <span>
                                Invited: {new Date(invitation.invited_at).toLocaleDateString()}
                              </span>
                            </div>
                            
                            <div className="flex gap-3">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleDeclineInvitation(invitation.id)}
                              >
                                Decline
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => handleAcceptInvitation(invitation.id)}
                              >
                                Accept Invitation
                              </Button>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                ))}
              </div>
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
        title="Delete Project?"
        description={`Are you sure you want to delete "${selectedProject?.name}"?`}
        details={[
          "All expert opinions",
          "All calculation results",
          "All invitations"
        ]}
        onConfirm={handleDeleteProject}
      />
    </div>
  );
};

export default Projects;
