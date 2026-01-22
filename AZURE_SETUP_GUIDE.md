# Azure Setup Guide: PostgreSQL + Blob Storage

Полное руководство по настройке Azure инфраструктуры для BeCoMe.

---

## Содержание

1. [Azure PostgreSQL Flexible Server](#1-azure-postgresql-flexible-server)
2. [Azure Blob Storage](#2-azure-blob-storage)
3. [Изменения в коде — Backend](#3-изменения-в-коде--backend)
4. [Изменения в коде — Frontend](#4-изменения-в-коде--frontend)
5. [Переменные окружения](#5-переменные-окружения)
6. [Тестирование](#6-тестирование)

---

## 1. Azure PostgreSQL Flexible Server

### 1.1 Создание сервера в Azure Portal

1. Войти в [Azure Portal](https://portal.azure.com)
2. **Create a resource** → поиск **Azure Database for PostgreSQL**
3. Выбрать **Flexible Server** → **Create**

#### Настройки сервера

| Параметр | Значение |
|----------|----------|
| Subscription | Ваша подписка |
| Resource group | `become-rg` (создать новую) |
| Server name | `become-db-server` |
| Region | `West Europe` (или ближайший) |
| PostgreSQL version | `16` |
| Workload type | `Development` (для начала) |
| Compute + storage | `Burstable, B1ms` (самый дешёвый) |

#### Аутентификация

| Параметр | Значение |
|----------|----------|
| Authentication method | `PostgreSQL authentication only` |
| Admin username | `become_admin` |
| Password | Сгенерировать надёжный пароль |

#### Networking

| Параметр | Значение |
|----------|----------|
| Connectivity method | `Public access (allowed IP addresses)` |
| Allow public access | ✅ Yes |
| Firewall rules | Add current client IP address |

5. **Review + create** → **Create**

### 1.2 Создание базы данных

После создания сервера:

1. Перейти в созданный сервер
2. **Databases** (левое меню) → **Add**
3. Database name: `become`
4. **Save**

### 1.3 Получение connection string

**Settings** → **Connect** → скопировать connection string:

```
postgresql://become_admin:<password>@become-db-server.postgres.database.azure.com:5432/become?sslmode=require
```

### 1.4 Альтернатива: Azure CLI

```bash
# Создание resource group
az group create --name become-rg --location westeurope

# Создание PostgreSQL сервера
az postgres flexible-server create \
    --resource-group become-rg \
    --name become-db-server \
    --location westeurope \
    --admin-user become_admin \
    --admin-password '<YOUR_PASSWORD>' \
    --sku-name Standard_B1ms \
    --tier Burstable \
    --version 16 \
    --storage-size 32 \
    --public-access 0.0.0.0

# Создание базы данных
az postgres flexible-server db create \
    --resource-group become-rg \
    --server-name become-db-server \
    --database-name become

# Добавление firewall rule для вашего IP
az postgres flexible-server firewall-rule create \
    --resource-group become-rg \
    --name become-db-server \
    --rule-name AllowMyIP \
    --start-ip-address <YOUR_IP> \
    --end-ip-address <YOUR_IP>
```

---

## 2. Azure Blob Storage

### 2.1 Создание Storage Account в Azure Portal

1. **Create a resource** → поиск **Storage account**
2. **Create**

#### Basics

| Параметр | Значение |
|----------|----------|
| Subscription | Ваша подписка |
| Resource group | `become-rg` |
| Storage account name | `becomestorage` (уникальное имя) |
| Region | `West Europe` |
| Performance | `Standard` |
| Redundancy | `LRS` (Locally-redundant) |

#### Advanced

| Параметр | Значение |
|----------|----------|
| Require secure transfer | ✅ Enabled |
| Allow Blob anonymous access | ✅ Enabled |
| Enable hierarchical namespace | ❌ Disabled |

3. **Review + create** → **Create**

### 2.2 Создание контейнера

1. Перейти в созданный Storage account
2. **Data storage** → **Containers** → **+ Container**

| Параметр | Значение |
|----------|----------|
| Name | `become-photos` |
| Anonymous access level | `Blob (anonymous read access for blobs only)` |

3. **Create**

### 2.3 Получение ключей доступа

1. **Security + networking** → **Access keys**
2. Скопировать:
   - **Storage account name**: `becomestorage`
   - **key1** → **Key**: `xxxxxxxxxxxxx`
   - **key1** → **Connection string**: `DefaultEndpointsProtocol=https;AccountName=...`

### 2.4 Альтернатива: Azure CLI

```bash
# Создание Storage Account
az storage account create \
    --name becomestorage \
    --resource-group become-rg \
    --location westeurope \
    --sku Standard_LRS \
    --kind StorageV2 \
    --allow-blob-public-access true

# Получение ключа
STORAGE_KEY=$(az storage account keys list \
    --resource-group become-rg \
    --account-name becomestorage \
    --query '[0].value' -o tsv)

# Создание контейнера
az storage container create \
    --name become-photos \
    --account-name becomestorage \
    --account-key $STORAGE_KEY \
    --public-access blob

# Получение connection string
az storage account show-connection-string \
    --resource-group become-rg \
    --name becomestorage \
    --query connectionString -o tsv
```

---

## 3. Изменения в коде — Backend

### 3.1 Добавить зависимость

В `pyproject.toml`:

```toml
[project.optional-dependencies]
api = [
    # ... существующие зависимости ...
    "azure-storage-blob>=12.19.0",
]
```

Установить:

```bash
uv sync --extra api
```

### 3.2 Обновить конфигурацию

В `api/config.py` добавить:

```python
class Settings(BaseSettings):
    # ... существующие поля ...

    # Azure Blob Storage (опционально — загрузка фото отключена если не настроено)
    azure_storage_connection_string: str | None = None
    azure_storage_account_name: str | None = None
    azure_storage_account_key: str | None = None
    azure_storage_container_name: str = "become-photos"

    @property
    def azure_storage_enabled(self) -> bool:
        """Check if Azure storage is properly configured."""
        return bool(
            self.azure_storage_connection_string
            and self.azure_storage_account_name
            and self.azure_storage_account_key
        )
```

### 3.3 Создать storage service

Создать директорию `api/services/storage/` с файлами:

#### `api/services/storage/__init__.py`

```python
"""Storage services for file operations."""
```

#### `api/services/storage/exceptions.py`

```python
"""Storage-specific exception hierarchy."""

from api.exceptions import BeCoMeAPIError


class StorageError(BeCoMeAPIError):
    """Base exception for storage operations."""


class StorageConfigurationError(StorageError):
    """Raised when storage is not properly configured."""


class StorageUploadError(StorageError):
    """Raised when file upload fails."""


class StorageDeleteError(StorageError):
    """Raised when file deletion fails."""
```

#### `api/services/storage/azure_blob_service.py`

```python
"""Azure Blob Storage service implementation."""

from uuid import uuid4

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.storage.blob import BlobServiceClient

from api.config import Settings
from api.services.storage.exceptions import (
    StorageConfigurationError,
    StorageDeleteError,
    StorageUploadError,
)


class AzureBlobStorageService:
    """Azure Blob Storage implementation for file operations."""

    ALLOWED_CONTENT_TYPES = frozenset({
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
    })
    MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

    def __init__(self, settings: Settings) -> None:
        """Initialize Azure Blob Storage client.

        :param settings: Application settings with Azure credentials
        :raises StorageConfigurationError: If Azure settings are missing
        """
        if not settings.azure_storage_connection_string:
            raise StorageConfigurationError(
                "Azure storage connection string not configured"
            )

        self._account_name = settings.azure_storage_account_name
        self._container_name = settings.azure_storage_container_name
        self._client = BlobServiceClient.from_connection_string(
            settings.azure_storage_connection_string
        )
        self._ensure_container_exists()

    def _ensure_container_exists(self) -> None:
        """Create container if it doesn't exist."""
        container_client = self._client.get_container_client(self._container_name)
        if not container_client.exists():
            container_client.create_container(public_access="blob")

    def _generate_blob_name(self, user_id: str, original_filename: str) -> str:
        """Generate unique blob name with user ID prefix."""
        extension = (
            original_filename.rsplit(".", 1)[-1].lower()
            if "." in original_filename
            else "jpg"
        )
        unique_id = uuid4().hex[:12]
        return f"profiles/{user_id}/{unique_id}.{extension}"

    def _extract_blob_name_from_url(self, file_url: str) -> str | None:
        """Extract blob name from a full Azure Blob URL."""
        expected_prefix = (
            f"https://{self._account_name}.blob.core.windows.net/"
            f"{self._container_name}/"
        )
        if file_url.startswith(expected_prefix):
            return file_url[len(expected_prefix) :].split("?")[0]
        return None

    def upload_file(
        self,
        file_content: bytes,
        file_name: str,
        content_type: str,
        user_id: str,
    ) -> str:
        """Upload a file to Azure Blob Storage.

        :param file_content: Raw file bytes
        :param file_name: Original filename
        :param content_type: MIME type
        :param user_id: User ID for organizing blobs
        :return: Public URL of uploaded blob
        :raises StorageUploadError: If upload fails
        """
        blob_name = self._generate_blob_name(user_id, file_name)
        blob_client = self._client.get_blob_client(
            container=self._container_name,
            blob=blob_name,
        )

        try:
            blob_client.upload_blob(
                file_content,
                content_type=content_type,
                overwrite=True,
            )
            return blob_client.url
        except AzureError as e:
            raise StorageUploadError(f"Failed to upload file: {e}") from e

    def delete_file(self, file_url: str) -> bool:
        """Delete a file from Azure Blob Storage.

        :param file_url: Public URL of the blob
        :return: True if deleted, False if not found
        :raises StorageDeleteError: If deletion fails unexpectedly
        """
        blob_name = self._extract_blob_name_from_url(file_url)
        if not blob_name:
            return False

        blob_client = self._client.get_blob_client(
            container=self._container_name,
            blob=blob_name,
        )

        try:
            blob_client.delete_blob()
            return True
        except ResourceNotFoundError:
            return False
        except AzureError as e:
            raise StorageDeleteError(f"Failed to delete file: {e}") from e
```

### 3.4 Миграция базы данных

Создать миграцию для `photo_url`:

```bash
cd /Users/katyabiser/Desktop/repos/BeCoMe
uv run alembic revision --autogenerate -m "add photo_url to users"
```

Содержимое миграции (проверить сгенерированный файл):

```python
def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("photo_url", sa.VARCHAR(length=500), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("photo_url")
```

Применить:

```bash
uv run alembic upgrade head
```

### 3.5 Обновить модель User

В `api/db/models.py` добавить поле:

```python
class User(SQLModel, table=True):
    # ... существующие поля ...
    photo_url: str | None = Field(default=None, max_length=500)
```

### 3.6 Обновить схему ответа

В `api/schemas/auth.py`:

```python
class UserResponse(BaseModel):
    """User profile response."""

    id: str
    email: str
    first_name: str
    last_name: str
    photo_url: str | None = None  # Добавить
```

### 3.7 Добавить dependency injection

В `api/dependencies.py`:

```python
from api.config import get_settings
from api.services.storage.azure_blob_service import AzureBlobStorageService


def get_storage_service() -> AzureBlobStorageService | None:
    """Create storage service if Azure is configured."""
    settings = get_settings()
    if not settings.azure_storage_enabled:
        return None
    return AzureBlobStorageService(settings)
```

### 3.8 Обновить UserService

В `api/services/user_service.py` добавить метод:

```python
def update_photo_url(self, user: User, photo_url: str | None) -> User:
    """Update user's profile photo URL.

    :param user: User to update
    :param photo_url: New photo URL or None to remove
    :return: Updated User instance
    """
    user.photo_url = photo_url
    self._session.add(user)
    self._session.commit()
    self._session.refresh(user)
    return user
```

### 3.9 Создать API эндпоинты

В `api/routes/users.py` добавить:

```python
from typing import Annotated

from fastapi import File, HTTPException, UploadFile, status

from api.dependencies import get_storage_service
from api.services.storage.azure_blob_service import AzureBlobStorageService
from api.services.storage.exceptions import StorageUploadError


@router.post(
    "/me/photo",
    response_model=UserResponse,
    summary="Upload profile photo",
)
async def upload_photo(
    current_user: CurrentUser,
    file: Annotated[
        UploadFile, File(description="Profile photo (JPEG, PNG, GIF, WebP, max 5MB)")
    ],
    user_service: Annotated[UserService, Depends(get_user_service)],
    storage_service: Annotated[
        AzureBlobStorageService | None, Depends(get_storage_service)
    ],
) -> UserResponse:
    """Upload or replace user profile photo."""
    if storage_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo upload is not available",
        )

    # Validate content type
    if file.content_type not in AzureBlobStorageService.ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Allowed: JPEG, PNG, GIF, WebP",
        )

    # Read and validate size
    content = await file.read()
    if len(content) > AzureBlobStorageService.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 5 MB",
        )

    # Delete old photo if exists
    if current_user.photo_url:
        storage_service.delete_file(current_user.photo_url)

    # Upload new photo
    try:
        photo_url = storage_service.upload_file(
            file_content=content,
            file_name=file.filename or "photo.jpg",
            content_type=file.content_type,
            user_id=str(current_user.id),
        )
    except StorageUploadError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to upload photo",
        )

    # Update user record
    updated_user = user_service.update_photo_url(current_user, photo_url)
    return UserResponse(
        id=str(updated_user.id),
        email=updated_user.email,
        first_name=updated_user.first_name,
        last_name=updated_user.last_name,
        photo_url=updated_user.photo_url,
    )


@router.delete(
    "/me/photo",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete profile photo",
)
def delete_photo(
    current_user: CurrentUser,
    user_service: Annotated[UserService, Depends(get_user_service)],
    storage_service: Annotated[
        AzureBlobStorageService | None, Depends(get_storage_service)
    ],
) -> None:
    """Remove user profile photo."""
    if not current_user.photo_url:
        return

    if storage_service:
        storage_service.delete_file(current_user.photo_url)

    user_service.update_photo_url(current_user, None)
```

---

## 4. Изменения в коде — Frontend

### 4.1 Обновить TypeScript типы

В `frontend/src/types/api.ts`:

```typescript
export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string | null;
  photo_url: string | null;  // Добавить
}
```

### 4.2 Добавить методы API клиента

В `frontend/src/lib/api.ts` добавить методы в класс `ApiClient`:

```typescript
async uploadPhoto(file: File): Promise<User> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${this.baseUrl}/users/me/photo`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${this.token}`,
      // НЕ устанавливать Content-Type — браузер сам добавит с boundary
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(error.detail || 'Failed to upload photo');
  }

  return response.json();
}

async deletePhoto(): Promise<void> {
  const response = await fetch(`${this.baseUrl}/users/me/photo`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${this.token}`,
    },
  });

  if (!response.ok) {
    throw new Error('Failed to delete photo');
  }
}
```

### 4.3 Обновить страницу Profile

В `frontend/src/pages/Profile.tsx` добавить UI загрузки фото:

```tsx
import { useRef, useState } from "react";
import { Camera, Trash2, Loader2 } from "lucide-react";

// В компоненте Profile добавить state и ref:
const [isUploadingPhoto, setIsUploadingPhoto] = useState(false);
const fileInputRef = useRef<HTMLInputElement>(null);

// Обработчики:
const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
  const file = e.target.files?.[0];
  if (!file) return;

  setIsUploadingPhoto(true);
  try {
    await api.uploadPhoto(file);
    await refreshUser();
    toast({ title: t("profile.toast.photoUpdated") });
  } catch (error) {
    toast({
      title: t("common.error"),
      description: error instanceof Error ? error.message : t("profile.toast.photoFailed"),
      variant: "destructive",
    });
  } finally {
    setIsUploadingPhoto(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }
};

const handleDeletePhoto = async () => {
  try {
    await api.deletePhoto();
    await refreshUser();
    toast({ title: t("profile.toast.photoDeleted") });
  } catch (error) {
    toast({
      title: t("common.error"),
      description: t("profile.toast.photoDeleteFailed"),
      variant: "destructive",
    });
  }
};

// В JSX заменить/обновить Avatar секцию:
<div className="relative inline-block">
  <Avatar className="h-24 w-24">
    {user.photo_url && <AvatarImage src={user.photo_url} alt={user.first_name} />}
    <AvatarFallback className="text-2xl">{initials}</AvatarFallback>
  </Avatar>
  <input
    ref={fileInputRef}
    type="file"
    accept="image/jpeg,image/png,image/gif,image/webp"
    className="hidden"
    onChange={handlePhotoUpload}
  />
  <div className="absolute -bottom-2 -right-2 flex gap-1">
    <Button
      size="icon"
      variant="secondary"
      className="h-8 w-8 rounded-full"
      onClick={() => fileInputRef.current?.click()}
      disabled={isUploadingPhoto}
    >
      {isUploadingPhoto ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <Camera className="h-4 w-4" />
      )}
    </Button>
    {user.photo_url && (
      <Button
        size="icon"
        variant="destructive"
        className="h-8 w-8 rounded-full"
        onClick={handleDeletePhoto}
      >
        <Trash2 className="h-4 w-4" />
      </Button>
    )}
  </div>
</div>
```

### 4.4 Добавить переводы

В `frontend/src/i18n/locales/en/profile.json`:

```json
{
  "toast": {
    "photoUpdated": "Profile photo updated",
    "photoFailed": "Failed to upload photo",
    "photoDeleted": "Profile photo removed",
    "photoDeleteFailed": "Failed to remove photo"
  }
}
```

В `frontend/src/i18n/locales/cs/profile.json`:

```json
{
  "toast": {
    "photoUpdated": "Profilová fotka aktualizována",
    "photoFailed": "Nepodařilo se nahrát fotku",
    "photoDeleted": "Profilová fotka odstraněna",
    "photoDeleteFailed": "Nepodařilo se odstranit fotku"
  }
}
```

---

## 5. Переменные окружения

### Локальная разработка (`.env`)

```bash
# Database
DATABASE_URL=sqlite:///./become.db

# JWT
SECRET_KEY=your-secret-key-here

# Azure Blob Storage (опционально для локальной разработки)
# AZURE_STORAGE_CONNECTION_STRING=...
# AZURE_STORAGE_ACCOUNT_NAME=...
# AZURE_STORAGE_ACCOUNT_KEY=...
# AZURE_STORAGE_CONTAINER_NAME=become-photos
```

### Production (`.env` или Azure App Settings)

```bash
# Database — Azure PostgreSQL
DATABASE_URL=postgresql://become_admin:<PASSWORD>@become-db-server.postgres.database.azure.com:5432/become?sslmode=require

# JWT
SECRET_KEY=<generate-with-openssl-rand-hex-32>

# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=becomestorage;AccountKey=xxx;EndpointSuffix=core.windows.net
AZURE_STORAGE_ACCOUNT_NAME=becomestorage
AZURE_STORAGE_ACCOUNT_KEY=<your-storage-key>
AZURE_STORAGE_CONTAINER_NAME=become-photos
```

### Обновить `.env.example`

```bash
# === Database ===
# SQLite for local development:
DATABASE_URL=sqlite:///./become.db
# PostgreSQL for production (Azure example):
# DATABASE_URL=postgresql://user:password@server.postgres.database.azure.com:5432/dbname?sslmode=require

# === JWT Authentication ===
# Generate with: openssl rand -hex 32
SECRET_KEY=your-secret-key-change-in-production

# === Azure Blob Storage (optional) ===
# Required for profile photo uploads
# AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=xxx;AccountKey=xxx;EndpointSuffix=core.windows.net
# AZURE_STORAGE_ACCOUNT_NAME=youraccountname
# AZURE_STORAGE_ACCOUNT_KEY=youraccountkey
# AZURE_STORAGE_CONTAINER_NAME=become-photos
```

---

## 6. Тестирование

### 6.1 Проверка подключения к PostgreSQL

```bash
# Проверить connection string
uv run python -c "
from api.db.engine import get_engine
engine = get_engine()
print(f'Database URL: {engine.url}')
with engine.connect() as conn:
    result = conn.execute(text('SELECT 1'))
    print('Connection successful!')
"
```

### 6.2 Проверка Blob Storage

```bash
# Проверить подключение к Azure Storage
uv run python -c "
from api.config import get_settings
from api.services.storage.azure_blob_service import AzureBlobStorageService

settings = get_settings()
if settings.azure_storage_enabled:
    service = AzureBlobStorageService(settings)
    print('Azure Blob Storage connected!')
    print(f'Container: {service._container_name}')
else:
    print('Azure Storage not configured')
"
```

### 6.3 Тест загрузки фото через API

```bash
# Получить токен
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}' \
  | jq -r '.access_token')

# Загрузить фото
curl -X POST http://localhost:8000/api/v1/users/me/photo \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/photo.jpg"

# Удалить фото
curl -X DELETE http://localhost:8000/api/v1/users/me/photo \
  -H "Authorization: Bearer $TOKEN"
```

### 6.4 Запуск тестов

```bash
# Unit тесты
uv run pytest tests/unit/ -v

# Integration тесты
uv run pytest tests/integration/ -v

# Все тесты с coverage
uv run pytest --cov=src --cov=api --cov-report=term-missing
```

---

## Чеклист готовности

- [ ] Azure PostgreSQL сервер создан
- [ ] База данных `become` создана
- [ ] Firewall rule добавлен для IP приложения
- [ ] Azure Storage Account создан
- [ ] Контейнер `become-photos` создан с public blob access
- [ ] Зависимость `azure-storage-blob` добавлена
- [ ] Миграция `photo_url` создана и применена
- [ ] API эндпоинты `/me/photo` работают
- [ ] Frontend загрузка фото работает
- [ ] Переводы добавлены (en + cs)
- [ ] Тесты проходят
