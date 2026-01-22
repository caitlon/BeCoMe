import { useState } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Loader2, AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Navbar } from "@/components/layout/Navbar";
import { DeleteConfirmModal } from "@/components/modals/DeleteConfirmModal";
import { ValidationChecklist, Requirement } from "@/components/forms";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

const NAME_REGEX = /^[\p{L}\s'-]+$/u;
const isValidName = (name: string) => !name || NAME_REGEX.test(name);

const getPasswordRequirements = (
  password: string,
  t: (key: string) => string
): Requirement[] => [
  {
    label: t("passwordRequirements.minLength"),
    met: password.length >= 8,
  },
  {
    label: t("passwordRequirements.uppercase"),
    met: /[A-Z]/.test(password),
  },
  {
    label: t("passwordRequirements.lowercase"),
    met: /[a-z]/.test(password),
  },
  {
    label: t("passwordRequirements.number"),
    met: /\d/.test(password),
  },
];

const Profile = () => {
  const { t } = useTranslation("profile");
  const { t: tAuth } = useTranslation("auth");
  const { user, refreshUser, logout } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();

  // Profile form
  const [firstName, setFirstName] = useState(user?.first_name || "");
  const [lastName, setLastName] = useState(user?.last_name || "");
  const [photoUrl, setPhotoUrl] = useState(user?.photo_url || "");
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [firstNameError, setFirstNameError] = useState<string | null>(null);
  const [lastNameError, setLastNameError] = useState<string | null>(null);

  const handleFirstNameChange = (value: string) => {
    setFirstName(value);
    if (value && !isValidName(value)) {
      setFirstNameError(tAuth("validation.nameFormat"));
    } else {
      setFirstNameError(null);
    }
  };

  const handleLastNameChange = (value: string) => {
    setLastName(value);
    if (value && !isValidName(value)) {
      setLastNameError(tAuth("validation.nameFormat"));
    } else {
      setLastNameError(null);
    }
  };

  const hasNameErrors = firstNameError !== null || lastNameError !== null;

  // Password form
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  const passwordRequirements = getPasswordRequirements(newPassword, tAuth);
  const allPasswordRequirementsMet = passwordRequirements.every((req) => req.met);

  // Delete account
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  const initials = user
    ? `${user.first_name[0]}${user.last_name?.[0] || ""}`.toUpperCase()
    : "";

  const handleSaveProfile = async () => {
    setIsSavingProfile(true);
    try {
      await api.updateCurrentUser({
        first_name: firstName,
        last_name: lastName || undefined,
        photo_url: photoUrl || undefined,
      });
      await refreshUser();
      toast({ title: t("toast.profileUpdated") });
    } catch (error) {
      toast({
        title: t("toast.error"),
        description:
          error instanceof Error ? error.message : t("toast.updateFailed"),
        variant: "destructive",
      });
    } finally {
      setIsSavingProfile(false);
    }
  };

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      toast({
        title: t("toast.error"),
        description: t("toast.passwordsNoMatch"),
        variant: "destructive",
      });
      return;
    }

    if (!allPasswordRequirementsMet) {
      toast({
        title: t("toast.error"),
        description: t("toast.passwordMin"),
        variant: "destructive",
      });
      return;
    }

    setIsChangingPassword(true);
    try {
      await api.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      toast({ title: t("toast.passwordUpdated") });
    } catch (error) {
      toast({
        title: t("toast.error"),
        description:
          error instanceof Error ? error.message : t("toast.passwordFailed"),
        variant: "destructive",
      });
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleDeleteAccount = async () => {
    try {
      await api.deleteAccount();
      logout();
      navigate("/");
      toast({ title: t("toast.accountDeleted") });
    } catch (error) {
      toast({
        title: t("toast.error"),
        description:
          error instanceof Error ? error.message : t("toast.deleteFailed"),
        variant: "destructive",
      });
    }
  };

  if (!user) {
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
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-lg mx-auto space-y-8"
        >
          {/* Profile Header */}
          <div className="text-center">
            <Avatar className="h-24 w-24 mx-auto mb-4">
              <AvatarImage src={user.photo_url || undefined} />
              <AvatarFallback className="text-2xl">{initials}</AvatarFallback>
            </Avatar>
            <h1 className="font-display text-2xl font-light">
              {user.first_name} {user.last_name}
            </h1>
            <p className="text-muted-foreground">{user.email}</p>
          </div>

          {/* Edit Profile */}
          <Card>
            <CardHeader>
              <CardTitle>{t("editProfile.title")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label htmlFor="firstName">{t("editProfile.firstName")}</Label>
                  <Input
                    id="firstName"
                    value={firstName}
                    onChange={(e) => handleFirstNameChange(e.target.value)}
                    className={cn(firstNameError && "border-destructive")}
                  />
                  {firstNameError && (
                    <p className="text-sm text-destructive">{firstNameError}</p>
                  )}
                </div>
                <div className="space-y-1">
                  <Label htmlFor="lastName">{t("editProfile.lastName")}</Label>
                  <Input
                    id="lastName"
                    value={lastName}
                    onChange={(e) => handleLastNameChange(e.target.value)}
                    className={cn(lastNameError && "border-destructive")}
                  />
                  {lastNameError && (
                    <p className="text-sm text-destructive">{lastNameError}</p>
                  )}
                </div>
              </div>

              <div>
                <Label htmlFor="photoUrl">{t("editProfile.photoUrl")}</Label>
                <Input
                  id="photoUrl"
                  type="url"
                  placeholder="https://..."
                  value={photoUrl}
                  onChange={(e) => setPhotoUrl(e.target.value)}
                />
              </div>

              <Button
                onClick={handleSaveProfile}
                disabled={isSavingProfile || !firstName || hasNameErrors}
                className="w-full"
              >
                {isSavingProfile ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  t("editProfile.save")
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Change Password */}
          <Card>
            <CardHeader>
              <CardTitle>{t("changePassword.title")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="currentPassword">
                  {t("changePassword.currentPassword")}
                </Label>
                <Input
                  id="currentPassword"
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="newPassword">
                  {t("changePassword.newPassword")}
                </Label>
                <Input
                  id="newPassword"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
                <ValidationChecklist
                  title={tAuth("passwordRequirements.title")}
                  requirements={passwordRequirements}
                  show={!!newPassword}
                />
              </div>

              <div>
                <Label htmlFor="confirmPassword">
                  {t("changePassword.confirmPassword")}
                </Label>
                <Input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </div>

              <Button
                onClick={handleChangePassword}
                disabled={
                  isChangingPassword ||
                  !currentPassword ||
                  !newPassword ||
                  !confirmPassword ||
                  !allPasswordRequirementsMet
                }
                className="w-full"
              >
                {isChangingPassword ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  t("changePassword.update")
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Danger Zone */}
          <Card className="border-destructive/50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-destructive">
                <AlertTriangle className="h-5 w-5" />
                {t("dangerZone.title")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-4">
                {t("dangerZone.warning")}
              </p>
              <Button
                variant="destructive"
                onClick={() => setDeleteModalOpen(true)}
              >
                {t("dangerZone.deleteButton")}
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      </main>

      <DeleteConfirmModal
        open={deleteModalOpen}
        onOpenChange={setDeleteModalOpen}
        title={t("deleteModal.title")}
        description={t("deleteModal.description")}
        details={[
          t("deleteModal.details.projects"),
          t("deleteModal.details.opinions"),
          t("deleteModal.details.noUndo"),
        ]}
        onConfirm={handleDeleteAccount}
        confirmText={t("deleteModal.confirm")}
      />
    </div>
  );
};

export default Profile;
