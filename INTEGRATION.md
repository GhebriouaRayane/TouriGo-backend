# Guide d'Intégration Frontend ↔ Backend

Ce document fournit une vue d'ensemble détaillée et des instructions pratiques pour l'intégration du frontend React existant avec le nouveau backend développé en FastAPI. Il couvre la configuration nécessaire, les endpoints de l'API, des exemples de requêtes, et les considérations de sécurité.

## 1. Configuration du Frontend

Pour assurer une communication correcte entre le frontend et le backend, il est essentiel de configurer l'URL de base de l'API dans le projet frontend. Il est recommandé d'utiliser une variable d'environnement pour cette configuration afin de faciliter le déploiement dans différents environnements (développement, staging, production).

**Exemple de configuration (fichier `src/api/config.ts` ou similaire) :**

```typescript
// src/api/config.ts
// Définir l'URL de base de l'API. En production, cette valeur devrait être chargée depuis les variables d'environnement.
export const API_BASE_URL = "http://localhost:8000/api/v1";

// Pour une gestion plus robuste des variables d'environnement en React/Vite, 
// vous pouvez utiliser import.meta.env.VITE_API_BASE_URL et configurer votre fichier .env.local
// Exemple: VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## 2. Endpoints de l'API

Le backend FastAPI expose les endpoints suivants pour interagir avec les fonctionnalités principales de l'application. La documentation Swagger UI est disponible à l'adresse `/docs` sur l'instance du backend (par exemple, `http://localhost:8000/docs`).

| Fonctionnalité | Méthode HTTP | Endpoint | Description | Authentification Requise |
| :--------------- | :----------- | :------- | :---------- | :----------------------- |
| **Authentification** | | | | |
| Demande de code d'inscription | `POST` | `/api/v1/auth/register` | Démarre l'inscription et envoie un code OTP (email/téléphone). | Non |
| Validation du code d'inscription | `POST` | `/api/v1/auth/register/verify-code` | Valide le code OTP et crée le compte utilisateur. | Non |
| Connexion et obtention de token | `POST` | `/api/v1/auth/login/access-token` | Authentifie un utilisateur et retourne un token JWT. | Non |
| Connexion Google | `POST` | `/api/v1/auth/login/google` | Authentifie avec un token Google ID et retourne un token JWT API. | Non |
| **Annonces (Listings)** | | | | |
| Récupérer toutes les annonces | `GET` | `/api/v1/listings/` | Récupère une liste paginée et filtrable d'annonces. | Non |
| Récupérer une annonce par ID | `GET` | `/api/v1/listings/{id}` | Récupère les détails d'une annonce spécifique. | Non |
| Créer une nouvelle annonce | `POST` | `/api/v1/listings/` | Permet à un utilisateur authentifié de créer une annonce. | Oui (JWT) |

## 2.1 Initialiser une base de données de démonstration

Pour remplir la base de données locale avec des utilisateurs, annonces, images, favoris, avis et réservations de test :

```bash
cd backend
./venv/bin/python scripts/seed_db.py
```

Comptes de démonstration créés :

- `admin@3ich.app` / `AdminPassword123!`
- `karim@3ich.app` / `HostPassword123!`
- `samira@3ich.app` / `HostPassword123!`
- `amina@3ich.app` / `UserPassword123!`
- `yacine@3ich.app` / `UserPassword123!`

## 3. Exemples de Requêtes Frontend (avec Axios)

Ces exemples illustrent comment le frontend peut interagir avec le backend en utilisant la bibliothèque `axios`.

### 3.1. Authentification de l'utilisateur

```typescript
import axios from 'axios';
import { API_BASE_URL } from './config'; // Assurez-vous que le chemin est correct

// Fonction de connexion
const loginUser = async (email, password) => {
  try {
    const formData = new FormData();
    formData.append('username', email); // FastAPI attend 'username' pour OAuth2PasswordRequestForm
    formData.append('password', password);

    const response = await axios.post(`${API_BASE_URL}/auth/login/access-token`, formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' } // Important pour OAuth2PasswordRequestForm
    });
    
    const { access_token, token_type } = response.data;
    localStorage.setItem('access_token', access_token); // Stocker le token pour les requêtes futures
    localStorage.setItem('token_type', token_type); // Stocker le type de token (généralement 'bearer')
    
    // Optionnel: Récupérer les informations de l'utilisateur après connexion
    // const userProfile = await axios.get(`${API_BASE_URL}/users/me`, { 
    //   headers: { Authorization: `${token_type} ${access_token}` }
    // });

    return response.data;
  } catch (error) {
    console.error("Erreur lors de la connexion:", error.response?.data || error.message);
    throw error;
  }
};

// 1) Demander un code OTP d'inscription
const requestRegisterCode = async (userData) => {
  try {
    const response = await axios.post(`${API_BASE_URL}/auth/register`, userData);
    return response.data;
  } catch (error) {
    console.error("Erreur lors de la demande de code:", error.response?.data || error.message);
    throw error;
  }
};

// 2) Valider le code OTP et finaliser l'inscription
const verifyRegisterCode = async (verificationId, code) => {
  try {
    const response = await axios.post(`${API_BASE_URL}/auth/register/verify-code`, {
      verification_id: verificationId,
      code,
    });
    return response.data;
  } catch (error) {
    console.error("Erreur lors de la validation du code:", error.response?.data || error.message);
    throw error;
  }
};
```

### 3.2. Récupération des annonces

```typescript
import axios from 'axios';
import { API_BASE_URL } from './config';

const fetchListings = async (filters = {}) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/listings/`, { params: filters });
    return response.data;
  } catch (error) {
    console.error("Erreur lors de la récupération des annonces:", error.response?.data || error.message);
    throw error;
  }
};

const fetchListingById = async (id) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/listings/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Erreur lors de la récupération de l'annonce ${id}:`, error.response?.data || error.message);
    throw error;
  }
};
```

### 3.3. Création d'une annonce (requiert authentification)

```typescript
import axios from 'axios';
import { API_BASE_URL } from './config';

const createListing = async (listingData) => {
  try {
    const access_token = localStorage.getItem('access_token');
    const token_type = localStorage.getItem('token_type') || 'Bearer';

    if (!access_token) {
      throw new Error("Aucun token d'authentification trouvé. Veuillez vous connecter.");
    }

    const response = await axios.post(`${API_BASE_URL}/listings/`, listingData, {
      headers: {
        'Authorization': `${token_type} ${access_token}`,
        'Content-Type': 'application/json' // FastAPI attend du JSON pour les Pydantic models
      }
    });
    return response.data;
  } catch (error) {
    console.error("Erreur lors de la création de l'annonce:", error.response?.data || error.message);
    throw error;
  }
};
```

## 4. Gestion des États Frontend

Pour une expérience utilisateur fluide, il est crucial de gérer les états de chargement, d'erreur et de succès des requêtes API. Des bibliothèques comme `React Query` (maintenant `TanStack Query`) ou `SWR` sont fortement recommandées pour simplifier cette gestion.

**Exemple avec `TanStack Query` :**

```typescript
import { useQuery, useMutation, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fetchListings, createListing } from './api-service'; // Votre fichier de services API

// Initialisation du client de requête (généralement dans App.tsx ou index.tsx)
const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <MyComponent />
    </QueryClientProvider>
  );
}

function MyComponent() {
  // Récupération des annonces
  const { data: listings, isLoading: listingsLoading, error: listingsError } = useQuery({
    queryKey: ['listings'],
    queryFn: () => fetchListings({ type: 'immobilier' }),
  });

  // Création d'une annonce
  const createListingMutation = useMutation({
    mutationFn: createListing,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['listings'] }); // Recharger les annonces après succès
      alert('Annonce créée avec succès!');
    },
    onError: (error) => {
      alert(`Erreur: ${error.message}`);
    },
  });

  if (listingsLoading) return <div>Chargement des annonces...</div>;
  if (listingsError) return <div>Erreur: {listingsError.message}</div>;

  return (
    <div>
      <h1>Nos Annonces</h1>
      {listings.map(listing => (
        <div key={listing.id}>{listing.title}</div>
      ))}
      <button onClick={() => createListingMutation.mutate({ title: 'Nouvelle Annonce', ... })}>Créer Annonce</button>
      {createListingMutation.isPending && <div>Création en cours...</div>}
      {createListingMutation.isError && <div>Erreur de création: {createListingMutation.error.message}</div>}
    </div>
  );
}
```

## 5. Sécurité

Le backend FastAPI intègre plusieurs mécanismes de sécurité essentiels :

*   **Authentification JWT (JSON Web Tokens)** : Les tokens d'accès sont générés après une connexion réussie et doivent être inclus dans l'en-tête `Authorization` de toutes les requêtes aux endpoints protégés (par exemple, `Bearer <token>`).
*   **Hachage des mots de passe** : Les mots de passe des utilisateurs sont hachés à l'aide de l'algorithme **bcrypt** avant d'être stockés en base de données, garantissant qu'ils ne sont jamais stockés en clair.
*   **CORS (Cross-Origin Resource Sharing)** : La politique CORS est configurée dans `app/main.py` pour autoriser les requêtes provenant des origines spécifiées dans le fichier `.env` (`ALLOWED_HOSTS`). Il est crucial de restreindre `ALLOWED_HOSTS` aux domaines de votre frontend en production pour éviter les attaques CSRF (Cross-Site Request Forgery).

**Exemple de configuration CORS dans `.env` :**

```
ALLOWED_HOSTS=["http://localhost:3000", "https://votre-domaine-frontend.com"]
```

**Variables OTP (email/SMS) dans `.env` :**

```env
REGISTRATION_CODE_LENGTH=6
REGISTRATION_CODE_EXPIRE_MINUTES=10
REGISTRATION_CODE_MAX_ATTEMPTS=5
AUTH_EXPOSE_DEBUG_CODE=false
GOOGLE_CLIENT_ID=votre_client_id_google.apps.googleusercontent.com

SMTP_HOST=smtp.votre-fournisseur.com
SMTP_PORT=587
SMTP_USERNAME=votre_user
SMTP_PASSWORD=votre_mot_de_passe
SMTP_FROM_EMAIL=no-reply@votre-domaine.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false

# Optionnel: envoi SMS via webhook interne
SMS_WEBHOOK_URL=
SMS_WEBHOOK_TOKEN=
```

## Conclusion

Ce guide fournit les informations nécessaires pour une intégration réussie du frontend React avec le backend FastAPI. En suivant ces directives, vous pouvez assurer une communication sécurisée et efficace entre les deux parties de votre application. Pour des détails supplémentaires sur les modèles de données et les schémas, veuillez consulter les fichiers `app/models/models.py` et `app/schemas/schemas.py` dans le projet backend.
