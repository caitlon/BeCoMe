import { useState, useEffect, useCallback } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
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
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
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
import { Navbar } from "@/components/layout/Navbar";
import { InviteExpertModal } from "@/components/modals/InviteExpertModal";
import { DeleteConfirmModal } from "@/components/modals/DeleteConfirmModal";
import { api } from "@/lib/api";
import { ProjectWithRole, Opinion, CalculationResult, Member } from "@/types/api";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";

const ProjectDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { toast } = useToast();

  const [project, setProject] = useState<ProjectWithRole | null>(null);
  const [opinions, setOpinions] = useState<Opinion[]>([]);
  const [result, setResult] = useState<CalculationResult | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSavingOpinion, setIsSavingOpinion] = useState(false);

  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [teamOpen, setTeamOpen] = useState(false);
  const [showIndividual, setShowIndividual] = useState(false);

  // Opinion form state
  const [position, setPosition] = useState("");
  const [lower, setLower] = useState("");
  const [peak, setPeak] = useState("");
  const [upper, setUpper] = useState("");

  const myOpinion = opinions.find((o) => o.user_id === user?.id);
  const otherOpinions = opinions.filter((o) => o.user_id !== user?.id);
  const isAdmin = project?.role === "admin";

  const fetchData = useCallback(async () => {
    if (!id) return;
    try {
      const [projectData, opinionsData, resultData, membersData] =
        await Promise.all([
          api.getProject(id),
          api.getOpinions(id),
          api.getResult(id),
          api.getMembers(id),
        ]);
      setProject(projectData);
      setOpinions(opinionsData);
      setResult(resultData);
      setMembers(membersData);

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
        title: "Error",
        description: "Failed to load project",
        variant: "destructive",
      });
      navigate("/projects");
    } finally {
      setIsLoading(false);
    }
  }, [id, user?.id, toast, navigate]);

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
        title: "Validation Error",
        description: "Please enter valid numbers",
        variant: "destructive",
      });
      return;
    }

    if (lowerNum > peakNum || peakNum > upperNum) {
      toast({
        title: "Validation Error",
        description: "Values must satisfy: lower ≤ peak ≤ upper",
        variant: "destructive",
      });
      return;
    }

    if (lowerNum < project.scale_min || upperNum > project.scale_max) {
      toast({
        title: "Validation Error",
        description: `Values must be within scale range: ${project.scale_min} — ${project.scale_max}`,
        variant: "destructive",
      });
      return;
    }

    setIsSavingOpinion(true);
    try {
      await api.createOrUpdateOpinion(id, {
        position: position || undefined,
        lower_bound: lowerNum,
        peak: peakNum,
        upper_bound: upperNum,
      });
      toast({ title: "Opinion saved" });
      fetchData();
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to save",
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
      toast({ title: "Opinion deleted" });
      fetchData();
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete opinion",
        variant: "destructive",
      });
    }
  };

  const handleDeleteProject = async () => {
    if (!id) return;
    try {
      await api.deleteProject(id);
      toast({ title: "Project deleted" });
      navigate("/projects");
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete project",
        variant: "destructive",
      });
    }
  };

  const handleRemoveMember = async (userId: string) => {
    if (!id) return;
    try {
      await api.removeMember(id, userId);
      toast({ title: "Member removed" });
      fetchData();
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to remove member",
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

  if (!project) {
    return null;
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      <main className="container mx-auto px-6 pt-24 pb-16">
        {/* Breadcrumb */}
        <div className="mb-6">
          <Link
            to="/projects"
            className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Projects
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
              Scale: {project.scale_min} — {project.scale_max} {project.scale_unit}
            </span>
            {isAdmin && (
              <div className="flex gap-2">
                <Button variant="outline" size="sm" className="gap-2">
                  <Edit className="h-4 w-4" />
                  Edit
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => setInviteModalOpen(true)}
                >
                  <UserPlus className="h-4 w-4" />
                  Invite Experts
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2 text-destructive hover:text-destructive"
                  onClick={() => setDeleteModalOpen(true)}
                >
                  <Trash2 className="h-4 w-4" />
                  Delete
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

            <OtherOpinionsTable opinions={otherOpinions} />
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
                Opinions
              </TabsTrigger>
              <TabsTrigger value="results" className="flex-1">
                Results
              </TabsTrigger>
              <TabsTrigger value="team" className="flex-1">
                Team
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
              <OtherOpinionsTable opinions={otherOpinions} />
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
                isAdmin={isAdmin}
                currentUserId={user?.id}
                onRemove={handleRemoveMember}
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
                className="w-full justify-between p-4 h-auto"
              >
                <span className="flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  Team ({members.length} members)
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
                isAdmin={isAdmin}
                currentUserId={user?.id}
                onRemove={handleRemoveMember}
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
        title="Delete Project?"
        description={`Are you sure you want to delete "${project.name}"?`}
        details={[
          `All expert opinions (${opinions.length})`,
          "All calculation results",
          "All invitations",
        ]}
        onConfirm={handleDeleteProject}
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
  const lowerNum = parseFloat(lower) || 0;
  const peakNum = parseFloat(peak) || 0;
  const upperNum = parseFloat(upper) || 0;
  const isValid =
    lowerNum <= peakNum &&
    peakNum <= upperNum &&
    lowerNum >= project.scale_min &&
    upperNum <= project.scale_max;

  return (
    <Card className="border-2 border-primary/20">
      <CardHeader>
        <CardTitle className="text-lg">Your Opinion</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <Label htmlFor="position">Position (optional)</Label>
          <Input
            id="position"
            placeholder="e.g., Head of Department"
            value={position}
            onChange={(e) => setPosition(e.target.value)}
          />
        </div>

        <div>
          <Label>Your Estimate</Label>
          <div className="grid grid-cols-3 gap-4 mt-2">
            <div>
              <Label className="text-xs text-muted-foreground">
                Lower (pessimistic)
              </Label>
              <Input
                type="number"
                placeholder={String(project.scale_min)}
                value={lower}
                onChange={(e) => setLower(e.target.value)}
                className="font-mono"
              />
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">
                Peak (most likely)
              </Label>
              <Input
                type="number"
                value={peak}
                onChange={(e) => setPeak(e.target.value)}
                className="font-mono"
              />
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">
                Upper (optimistic)
              </Label>
              <Input
                type="number"
                placeholder={String(project.scale_max)}
                value={upper}
                onChange={(e) => setUpper(e.target.value)}
                className="font-mono"
              />
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Range: {project.scale_min} — {project.scale_max} {project.scale_unit}
          </p>
        </div>

        {/* Mini Triangle Preview */}
        {lower && peak && upper && isValid && (
          <div className="bg-muted rounded p-4">
            <svg viewBox="0 0 200 60" className="w-full h-12">
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

        <div className="flex gap-3">
          <Button
            onClick={onSave}
            disabled={isSaving || !lower || !peak || !upper}
            className="flex-1"
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : myOpinion ? (
              "Update Opinion"
            ) : (
              "Save Opinion"
            )}
          </Button>
        </div>

        {myOpinion && (
          <button
            onClick={onDelete}
            className="text-sm text-destructive hover:underline"
          >
            Delete my opinion
          </button>
        )}
      </CardContent>
    </Card>
  );
};

const OtherOpinionsTable = ({ opinions }: { opinions: Opinion[] }) => {
  if (opinions.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Other Opinions</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-center py-8">
            No other opinions yet
          </p>
        </CardContent>
      </Card>
    );
  }

  const sorted = [...opinions].sort((a, b) => b.centroid - a.centroid);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Other Opinions</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Expert</TableHead>
              <TableHead className="text-right font-mono">L</TableHead>
              <TableHead className="text-right font-mono">P</TableHead>
              <TableHead className="text-right font-mono">U</TableHead>
              <TableHead className="text-right font-mono">Centroid</TableHead>
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
  if (!result || opinions.length === 0) {
    return (
      <Card>
        <CardContent className="py-16 text-center">
          <p className="text-muted-foreground">
            Results will appear once experts submit their opinions.
          </p>
        </CardContent>
      </Card>
    );
  }

  const scaleRange = project.scale_max - project.scale_min;
  const errorPercent = (result.max_error / scaleRange) * 100;

  return (
    <div className="space-y-6">
      {/* Best Compromise */}
      <Card className="border-2 border-primary">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Best Compromise
            <span className="text-sm font-normal text-muted-foreground">
              (ΓΩMean)
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 text-center mb-4">
            <div>
              <div className="text-xs text-muted-foreground uppercase">Lower</div>
              <div className="font-mono text-2xl font-medium">
                {result.best_compromise.lower.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground uppercase">Peak</div>
              <div className="font-mono text-2xl font-medium">
                {result.best_compromise.peak.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground uppercase">Upper</div>
              <div className="font-mono text-2xl font-medium">
                {result.best_compromise.upper.toFixed(2)}
              </div>
            </div>
          </div>
          <div className="text-center border-t pt-4">
            <div className="text-xs text-muted-foreground uppercase">Centroid</div>
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
            <CardTitle className="text-sm">Arithmetic Mean (Γ)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="font-mono text-sm">
              {result.arithmetic_mean.lower.toFixed(2)} |{" "}
              {result.arithmetic_mean.peak.toFixed(2)} |{" "}
              {result.arithmetic_mean.upper.toFixed(2)}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              Centroid: {result.arithmetic_mean.centroid.toFixed(2)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Median (Ω)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="font-mono text-sm">
              {result.median.lower.toFixed(2)} | {result.median.peak.toFixed(2)} |{" "}
              {result.median.upper.toFixed(2)}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              Centroid: {result.median.centroid.toFixed(2)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Max Error & Experts */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm">Max Error (Δmax)</span>
            <span className="font-mono font-medium">
              {result.max_error.toFixed(2)}
            </span>
          </div>
          <Progress value={Math.min(errorPercent, 100)} className="h-2" />
          <div className="flex justify-between items-center mt-4 text-sm text-muted-foreground">
            <span>Experts</span>
            <span className="font-mono">{result.num_experts}</span>
          </div>
        </CardContent>
      </Card>

      {/* Visualization */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Visualization</CardTitle>
        </CardHeader>
        <CardContent>
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
                <span>Mean</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-0.5 bg-green-500" />
                <span>Median</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-0.5 bg-foreground" />
                <span>Best</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="showIndividual"
                checked={showIndividual}
                onCheckedChange={(checked) => setShowIndividual(!!checked)}
              />
              <Label htmlFor="showIndividual" className="text-xs cursor-pointer">
                Show individual opinions
              </Label>
            </div>
          </div>
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
  const scaleToX = (value: number) => {
    return (
      40 +
      ((value - project.scale_min) / (project.scale_max - project.scale_min)) * 320
    );
  };

  const baseY = 160;
  const peakY = 30;

  return (
    <svg viewBox="0 0 400 200" className="w-full">
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
  isAdmin: boolean;
  currentUserId?: string;
  onRemove: (userId: string) => void;
}

const TeamTable = ({
  members,
  isAdmin,
  currentUserId,
  onRemove,
}: TeamTableProps) => {
  return (
    <Card>
      <CardContent className="pt-6">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Joined</TableHead>
              {isAdmin && <TableHead></TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {members.map((member) => (
              <TableRow key={member.user_id}>
                <TableCell className="font-medium">
                  {member.first_name} {member.last_name}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {member.email}
                </TableCell>
                <TableCell>
                  <Badge
                    variant={member.role === "admin" ? "default" : "secondary"}
                  >
                    {member.role}
                  </Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {new Date(member.joined_at).toLocaleDateString()}
                </TableCell>
                {isAdmin && (
                  <TableCell>
                    {member.role !== "admin" &&
                      member.user_id !== currentUserId && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive hover:text-destructive"
                          onClick={() => onRemove(member.user_id)}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      )}
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
};

export default ProjectDetail;
