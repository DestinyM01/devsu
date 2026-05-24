# Andujar Online — Plataforma Azure IaC

Infraestructura como Código (IaC) empresarial para una API REST de producción construida con Django, contenerizada con Docker, orquestada con Kubernetes en Azure AKS, automatizada con Azure DevOps CI/CD y provisionada con Terraform.

---

## Tabla de Contenidos

- [Arquitectura](#arquitectura)
- [Aplicación](#aplicación)
- [Desarrollo Local](#desarrollo-local)
- [Docker](#docker)
- [Pipeline CI/CD (Azure DevOps)](#pipeline-cicd-azure-devops)
- [Despliegue en Kubernetes](#despliegue-en-kubernetes)
- [Infraestructura como Código (Terraform)](#infraestructura-como-código-terraform)
- [Decisiones de Diseño](#decisiones-de-diseño)
- [Consideraciones de Producción](#consideraciones-de-producción)

---

## Arquitectura

### Arquitectura de Alto Nivel

```mermaid
graph TB
    subgraph "Azure DevOps"
        REPO[Azure Repos / GitHub]
        PIPE[Azure Pipelines CI/CD]
    end

    subgraph "Azure Cloud"
        ACR[Azure Container Registry]
        subgraph "Clúster AKS"
            ING[Ingress Controller<br/>nginx]
            subgraph "namespace andujar-online"
                SVC[Service<br/>ClusterIP:80]
                CM[ConfigMap]
                SEC[Secret]
                HPA[HorizontalPodAutoscaler]
                subgraph "Deployment - 2+ réplicas"
                    POD1[Pod 1<br/>Django + Gunicorn]
                    POD2[Pod 2<br/>Django + Gunicorn]
                end
            end
        end
    end

    USER[Usuario / Cliente] -->|HTTPS| ING
    ING --> SVC
    SVC --> POD1
    SVC --> POD2
    CM -.->|env vars| POD1
    CM -.->|env vars| POD2
    SEC -.->|secrets| POD1
    SEC -.->|secrets| POD2
    HPA -.->|auto-escalar| POD1
    HPA -.->|auto-escalar| POD2
    REPO -->|trigger| PIPE
    PIPE -->|build & push| ACR
    PIPE -->|deploy| ING
    ACR -.->|pull imagen| POD1
    ACR -.->|pull imagen| POD2
```

### Flujo del Pipeline CI/CD

```mermaid
graph LR
    A[Push de Código] --> B[Instalar Deps]
    B --> C[Ruff Linter]
    C --> D[Tests Unitarios]
    D --> E[Cobertura de Código]
    E --> F[Docker Build & Push ACR]
    F --> G[Escaneo Vuln Trivy]
    G --> H[Desplegar en AKS]

    style A fill:#2196F3,stroke:#1565C0,color:#fff
    style F fill:#FF9800,stroke:#E65100,color:#fff
    style H fill:#4CAF50,stroke:#2E7D32,color:#fff
```

---

## Aplicación

API REST construida con **Django 4.2** + **Django REST Framework 3.14**, usando SQLite.

### Endpoints de la API

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/users/` | GET | Listar todos los usuarios |
| `/api/users/` | POST | Crear un usuario (`{"dni": "...", "name": "..."}`) |
| `/api/users/<id>/` | GET | Obtener usuario por ID |
| `/health/` | GET | Verificación de salud (probes de K8s) |
| `/admin/` | GET | Panel de administración de Django |

---

## Desarrollo Local

### Prerrequisitos

- Python 3.11+
- Docker (para ejecución contenerizada)
- Azure CLI + kubectl + Terraform (para despliegue en la nube)

### Ejecutar la Aplicación

```bash
# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements-dev.txt

# Ejecutar migraciones
python manage.py migrate

# Ejecutar la aplicación
python manage.py runserver

# Abrir: http://localhost:8000/api/
```

### Ejecutar Tests

```bash
# Ejecutar tests unitarios
python manage.py test --verbosity=2

# Ejecutar con cobertura
coverage run manage.py test
coverage report
coverage html && open htmlcov/index.html
```

### Lint

```bash
# Análisis estático
ruff check api/ demo/

# Verificación de formato
ruff format --check api/ demo/
```

---

## Docker

### Construir y Ejecutar

```bash
# Construir
docker build -t andujar-online-api:latest .

# Ejecutar
docker run -d --name andujar-online -p 8000:8000 \
  -e DJANGO_SECRET_KEY="tu-clave-secreta" \
  andujar-online-api:latest

# Probar
curl http://localhost:8000/health/
curl http://localhost:8000/api/users/
```

### Características del Dockerfile

| Característica | Detalle |
|---|---|
| Build multi-etapa | Imagen de producción más pequeña (~150MB) |
| Gunicorn | Servidor WSGI de producción (3 workers) |
| Usuario no-root | `appuser` por seguridad |
| Health check | `HEALTHCHECK` integrado en `/health/` |
| Archivos estáticos | `collectstatic` durante el build |
| Migraciones | Aplicadas durante el build para SQLite |

---

## Pipeline CI/CD (Azure DevOps)

El pipeline está definido en `azure-pipelines.yml`.

### Etapas del Pipeline

| Etapa | Herramientas | Propósito |
|---|---|---|
| **Build & Test** | pip, ruff, coverage | Instalar deps, lint, test, reporte de cobertura |
| **Docker** | Docker, ACR, Trivy | Construir imagen, push a ACR, escaneo de vulnerabilidades |
| **Deploy** | KubernetesManifest | Aplicar manifiestos K8s en AKS |

### Configuración en Azure DevOps

1. **Crear un proyecto en Azure DevOps** e importar/vincular tu repositorio de GitHub
2. **Crear una Service Connection** a Azure (Settings → Service connections → Azure Resource Manager)
3. **Actualizar `azure-pipelines.yml`** con las variables:
   ```yaml
   azureSubscription: 'nombre-de-tu-service-connection'
   acrName: 'tunombreacr'
   aksResourceGroup: 'nombre-de-tu-rg'
   aksClusterName: 'nombre-de-tu-aks'
   ```
4. **Crear un pipeline** apuntando a `azure-pipelines.yml`

---

## Despliegue en Kubernetes

### Manifiestos

| Archivo | Recurso | Descripción |
|---|---|---|
| `namespace.yml` | Namespace | Namespace `andujar-online` |
| `configmap.yml` | ConfigMap | DEBUG, ALLOWED_HOSTS, DATABASE_NAME |
| `secret.yml` | Secret | DJANGO_SECRET_KEY (base64) |
| `deployment.yml` | Deployment | 2 réplicas, probes, límites de recursos, rolling update |
| `service.yml` | Service | ClusterIP:80 → contenedor:8000 |
| `ingress.yml` | Ingress | Ingress nginx con enrutamiento por dominio |
| `hpa.yml` | HPA | 2–5 réplicas, autoescalado por CPU/memoria |

### Despliegue Manual en AKS

```bash
# Obtener credenciales de AKS
az aks get-credentials --resource-group andujar-online-rg --name andujar-online-aks

# Aplicar todos los manifiestos
kubectl apply -f k8s/namespace.yml
kubectl apply -f k8s/configmap.yml
kubectl apply -f k8s/secret.yml
kubectl apply -f k8s/deployment.yml
kubectl apply -f k8s/service.yml
kubectl apply -f k8s/ingress.yml
kubectl apply -f k8s/hpa.yml

# Verificar
kubectl get all -n andujar-online
kubectl get hpa -n andujar-online
```

### Pruebas Locales (Minikube)

```bash
minikube start
minikube addons enable ingress
minikube addons enable metrics-server

eval $(minikube docker-env)
docker build -t andujar-online-api:latest .

# Actualizar deployment.yml: imagePullPolicy: Never
kubectl apply -f k8s/

kubectl port-forward -n andujar-online svc/andujar-online-api 8000:80
curl http://localhost:8000/health/
```

---

## Infraestructura como Código (Terraform)

El directorio `terraform/` provisiona toda la infraestructura en Azure.

### Recursos Creados

| Recurso | Propósito |
|---|---|
| Resource Group | Contenedor para todos los recursos de Azure |
| Azure Container Registry | Almacenamiento de imágenes Docker |
| Clúster AKS | Clúster de Kubernetes con nodos autoescalables |
| Role Assignment | AcrPull — permite a AKS obtener imágenes de ACR |

### Uso

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Editar terraform.tfvars con tus valores

az login
terraform init
terraform plan
terraform apply

# Configurar kubectl
az aks get-credentials --resource-group andujar-online-rg --name andujar-online-aks

# Cuando termines:
terraform destroy
```

---

## Decisiones de Diseño

| Decisión | Justificación |
|---|---|
| **Django** | Framework robusto con soporte nativo para REST API, ORM y panel de administración |
| **Gunicorn** | Servidor WSGI de producción, reemplaza el servidor de desarrollo de Django |
| **Azure DevOps** | El usuario tiene acceso a Azure DevOps; integración nativa con AKS/ACR |
| **Azure ACR** | Integración estrecha con AKS mediante identidad administrada (AcrPull) |
| **Docker multi-etapa** | Imagen más pequeña, solo dependencias de producción en la etapa final |
| **2 réplicas + HPA** | Requisito de alta disponibilidad; autoescala de 2→5 según la carga |
| **Rolling update** | Despliegues sin tiempo de inactividad (`maxUnavailable: 0`) |
| **Contenedor no-root** | Mejor práctica de seguridad a nivel de Docker y K8s |
| **Endpoint de salud** | Se agregó `/health/` para las probes de liveness/readiness/startup de K8s |
| **Terraform para Azure** | Infraestructura reproducible, versionada y auditada como código |
| **Nodos Standard_B2s** | Costo-eficientes en producción; rendimiento con capacidad de ráfaga |

---

## Consideraciones de Producción

| Área | Recomendación |
|---|---|
| **TLS/SSL** | Usar cert-manager + Let's Encrypt en AKS |
| **DNS** | Apuntar dominio personalizado a la IP externa del Ingress de AKS |
| **Secretos** | Usar Azure Key Vault con el driver CSI en lugar de secretos de K8s |
| **Base de datos** | Reemplazar SQLite con Azure Database para PostgreSQL |
| **Monitoreo** | Azure Monitor + Container Insights para métricas y logs |
| **Respaldo** | Velero para respaldo del clúster |
| **Políticas de red** | Restringir tráfico entre pods con Calico/Azure NPM |
| **RBAC** | Integración con Azure AD para control de acceso granular en K8s |
| **Pod Disruption Budget** | Asegurar disponibilidad durante actualizaciones de nodos |

---

## Estructura del Proyecto

```
.
├── azure-pipelines.yml        # Pipeline CI/CD de Azure DevOps
├── api/                       # Aplicación Django REST Framework
│   ├── models.py              # Modelo User
│   ├── views.py               # ViewSet + health check
│   ├── serializers.py         # Serializador de User
│   ├── urls.py                # Enrutamiento de la API
│   ├── tests.py               # Tests unitarios (11 tests)
│   ├── admin.py               # Registro en admin
│   └── migrations/            # Migraciones de base de datos
├── demo/                      # Configuración del proyecto Django
│   ├── settings.py            # Settings (configurable por env)
│   ├── urls.py                # URLs raíz + health
│   ├── wsgi.py                # Configuración WSGI
│   └── asgi.py                # Configuración ASGI
├── k8s/                       # Manifiestos de Kubernetes
│   ├── namespace.yml
│   ├── configmap.yml
│   ├── secret.yml
│   ├── deployment.yml         # 2+ réplicas, probes
│   ├── service.yml
│   ├── ingress.yml
│   └── hpa.yml                # Autoescalado
├── terraform/                 # IaC de Azure (Terraform)
│   ├── main.tf                # RG, ACR, AKS
│   ├── variables.tf
│   ├── outputs.tf
│   └── terraform.tfvars.example
├── Dockerfile                 # Multi-etapa, gunicorn
├── .dockerignore
├── .gitignore
├── manage.py
├── requirements.txt           # Dependencias de producción
├── requirements-dev.txt       # Dependencias de dev/test
├── pyproject.toml             # Configuración de Ruff + cobertura
└── README.md
```

---

## Licencia

Copyright © 2026 Andujar Online. Todos los derechos reservados.
