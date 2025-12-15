# Frontend Dashboard Implementation Guide (JavaScript/TypeScript)

**Status:** 📋 Planned (Not Started)  
**Priority:** Medium (after Phase 3 completion)  
**Estimated Effort:** 2-3 days (basic), 1-2 weeks (full-featured)  
**Created:** December 15, 2025

---

## Overview

This document outlines the plan for building a web dashboard for Voice Ledger using **JavaScript/TypeScript** (React/Next.js) instead of Python-based UI frameworks.

**Key Decision:** Backend (FastAPI Python) stays unchanged; only frontend is built in JavaScript.

---

## Why JavaScript Frontend?

### Current Architecture (Already Perfect for This!)
✅ FastAPI backend with **REST API** (returns JSON)  
✅ Backend and frontend **already decoupled**  
✅ All business logic in Python (no changes needed)  

### Advantages of JavaScript/TypeScript:

| Feature | Python (Streamlit) | JavaScript (React/Next.js) |
|---------|-------------------|---------------------------|
| **Performance** | Server-side rendering | Client-side, faster |
| **Mobile-responsive** | Limited | Excellent |
| **Real-time updates** | Polling only | WebSockets supported |
| **UI Libraries** | Basic components | Massive ecosystem |
| **Deployment** | Must run Python server | Static hosting (Vercel, Netlify) |
| **Customization** | Limited | Unlimited |
| **Developer ecosystem** | Small | Huge |
| **Production-ready** | Internal tools only | Enterprise-grade |

---

## Recommended Tech Stack

### Option 1: Next.js (Recommended - Full-Stack Framework)

```bash
# Create new Next.js app
npx create-next-app@latest voice-ledger-dashboard
cd voice-ledger-dashboard

# Install dependencies
npm install axios date-fns
npm install -D @types/node

# Run development server
npm run dev  # Available at http://localhost:3000
```

**Pros:**
- Built-in routing
- API routes (can proxy to FastAPI)
- Server-side rendering (SEO-friendly)
- Easy deployment (Vercel)
- TypeScript support out-of-the-box

### Option 2: React + Vite (Lightweight Alternative)

```bash
# Create Vite app with React + TypeScript
npm create vite@latest voice-ledger-dashboard -- --template react-ts
cd voice-ledger-dashboard

# Install dependencies
npm install axios react-router-dom
npm install

# Run development server
npm run dev  # Available at http://localhost:5173
```

**Pros:**
- Faster build times
- Simpler setup
- Smaller bundle size
- Good for single-page apps

---

## Architecture

### Current Setup (No Changes Needed)

```
┌─────────────────────┐
│   FastAPI Backend   │ ← Your existing Python code
│   (Port 8000)       │
│                     │
│  - Voice API        │
│  - Database         │
│  - Celery Workers   │
│  - Blockchain       │
└──────────┬──────────┘
           │ REST API (JSON)
           │
┌──────────▼──────────┐
│  JavaScript         │ ← New frontend (to be built)
│  Frontend           │
│  (Port 3000)        │
│                     │
│  - React/Next.js    │
│  - UI Components    │
│  - State Management │
└─────────────────────┘
```

### Communication

Frontend → Backend:
- HTTP requests to `http://localhost:8000` (development)
- HTTPS to production API URL
- Authentication via `X-API-Key` header

---

## Dashboard Features (MVP)

### Page 1: Voice Upload
**Route:** `/upload`

**Features:**
- Audio file upload (drag & drop)
- Live recording from microphone
- Format validation (WAV, MP3, M4A, OGG)
- Progress bar during upload
- Real-time status updates (polling `/voice/status/{task_id}`)
- Display results (transcript, intent, entities, batch ID)

### Page 2: Batch List
**Route:** `/batches`

**Features:**
- Table of all batches
- Filters (date range, farmer, coffee type, quality grade)
- Search functionality
- Pagination (50 batches per page)
- Export to CSV
- Click batch → view details

### Page 3: Batch Details
**Route:** `/batch/{id}`

**Features:**
- Full batch information
- Farmer details
- DPP viewer
- QR code display
- Blockchain verification link
- IPFS link to stored data
- Event history timeline

### Page 4: DPP Viewer
**Route:** `/dpp/{id}`

**Features:**
- Formatted Digital Product Passport
- Printable view
- QR code for consumer scanning
- Traceability map (geolocation visualization)
- Farmer profile
- Certifications (organic, fair trade)

### Page 5: Analytics Dashboard
**Route:** `/analytics`

**Features:**
- Total batches created (chart over time)
- Voice command accuracy metrics
- Top farmers (by volume)
- Coffee type distribution (pie chart)
- Processing time trends
- Geographic distribution map

---

## API Integration Examples

### 1. Voice Upload (Async)

```typescript
// lib/api.ts
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY;

export async function uploadAudio(file: File): Promise<{ task_id: string }> {
  const formData = new FormData();
  formData.append('audio', file);
  
  const response = await fetch(`${API_BASE_URL}/voice/upload-async`, {
    method: 'POST',
    headers: {
      'X-API-Key': API_KEY!,
    },
    body: formData,
  });
  
  if (!response.ok) {
    throw new Error(`Upload failed: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getTaskStatus(taskId: string) {
  const response = await fetch(`${API_BASE_URL}/voice/status/${taskId}`, {
    headers: {
      'X-API-Key': API_KEY!,
    },
  });
  
  return response.json();
}
```

### 2. Batch List with Pagination

```typescript
export async function getBatches(page: number = 1, limit: number = 50) {
  const response = await fetch(
    `${API_BASE_URL}/batches?page=${page}&limit=${limit}`,
    {
      headers: {
        'X-API-Key': API_KEY!,
      },
    }
  );
  
  return response.json();
}
```

### 3. DPP Generation

```typescript
export async function generateDPP(batchId: string) {
  const response = await fetch(`${API_BASE_URL}/dpp/generate`, {
    method: 'POST',
    headers: {
      'X-API-Key': API_KEY!,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ batch_id: batchId }),
  });
  
  return response.json();
}
```

---

## UI Components to Build

### 1. AudioUploader Component

```typescript
// components/AudioUploader.tsx
import { useState } from 'react';

export function AudioUploader() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  
  const handleUpload = async () => {
    if (!file) return;
    
    setUploading(true);
    try {
      const { task_id } = await uploadAudio(file);
      setTaskId(task_id);
      // Start polling for status
      pollTaskStatus(task_id);
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      setUploading(false);
    }
  };
  
  return (
    <div className="audio-uploader">
      <input 
        type="file" 
        accept="audio/*"
        onChange={(e) => setFile(e.target.files?.[0] || null)}
      />
      <button onClick={handleUpload} disabled={!file || uploading}>
        {uploading ? 'Uploading...' : 'Upload Audio'}
      </button>
      {taskId && <TaskStatusDisplay taskId={taskId} />}
    </div>
  );
}
```

### 2. TaskStatusDisplay Component

```typescript
// components/TaskStatusDisplay.tsx
import { useState, useEffect } from 'react';

export function TaskStatusDisplay({ taskId }: { taskId: string }) {
  const [status, setStatus] = useState<any>(null);
  
  useEffect(() => {
    const interval = setInterval(async () => {
      const data = await getTaskStatus(taskId);
      setStatus(data);
      
      if (data.status === 'completed' || data.status === 'error') {
        clearInterval(interval);
      }
    }, 1000);
    
    return () => clearInterval(interval);
  }, [taskId]);
  
  if (!status) return <div>Loading...</div>;
  
  return (
    <div className="task-status">
      <h3>Processing Status: {status.status}</h3>
      {status.progress && <ProgressBar progress={status.progress} />}
      {status.result && <ResultDisplay result={status.result} />}
    </div>
  );
}
```

### 3. BatchTable Component

```typescript
// components/BatchTable.tsx
export function BatchTable({ batches }: { batches: Batch[] }) {
  return (
    <table className="batch-table">
      <thead>
        <tr>
          <th>Batch ID</th>
          <th>Coffee Type</th>
          <th>Quantity</th>
          <th>Quality Grade</th>
          <th>Farmer</th>
          <th>Date</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {batches.map((batch) => (
          <tr key={batch.id}>
            <td>{batch.batch_id}</td>
            <td>{batch.coffee_type}</td>
            <td>{batch.quantity_kg} kg</td>
            <td>{batch.quality_grade}</td>
            <td>{batch.farmer_name}</td>
            <td>{formatDate(batch.created_at)}</td>
            <td>
              <a href={`/batch/${batch.id}`}>View</a>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

---

## Styling Options

### Option 1: Tailwind CSS (Recommended)

```bash
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

**Pros:**
- Utility-first CSS
- Fast development
- Small bundle size
- Great for responsive design

### Option 2: Material-UI (MUI)

```bash
npm install @mui/material @emotion/react @emotion/styled
```

**Pros:**
- Pre-built components
- Professional look out-of-the-box
- Good accessibility

### Option 3: shadcn/ui (Modern Choice)

```bash
npx shadcn-ui@latest init
npx shadcn-ui@latest add button card table
```

**Pros:**
- Copy-paste components
- Built on Radix UI + Tailwind
- Highly customizable

---

## Real-Time Features

### WebSocket Support for Live Updates

```typescript
// lib/websocket.ts
export function connectWebSocket(taskId: string) {
  const ws = new WebSocket(`ws://localhost:8000/ws/task/${taskId}`);
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Task update:', data);
    // Update UI with new status
  };
  
  ws.onclose = () => {
    console.log('WebSocket closed');
  };
  
  return ws;
}
```

**Note:** Requires FastAPI WebSocket endpoint (can be added later)

---

## State Management

### Option 1: React Context (Simple)

```typescript
// context/AppContext.tsx
export const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [user, setUser] = useState<User | null>(null);
  
  return (
    <AppContext.Provider value={{ batches, setBatches, user, setUser }}>
      {children}
    </AppContext.Provider>
  );
}
```

### Option 2: Zustand (Recommended for Larger Apps)

```bash
npm install zustand
```

```typescript
// store/useStore.ts
import create from 'zustand';

export const useStore = create((set) => ({
  batches: [],
  setBatches: (batches) => set({ batches }),
  addBatch: (batch) => set((state) => ({ 
    batches: [...state.batches, batch] 
  })),
}));
```

---

## Deployment

### Development
```bash
# Start FastAPI backend
cd Voice-Ledger
uvicorn voice.service.api:app --reload

# Start Next.js frontend (separate terminal)
cd voice-ledger-dashboard
npm run dev
```

### Production

**Backend (FastAPI):**
- Deploy to: Railway, Render, Fly.io, AWS, GCP
- URL: `https://api.voice-ledger.com`

**Frontend (Next.js):**
- Deploy to: Vercel (recommended), Netlify, Cloudflare Pages
- URL: `https://dashboard.voice-ledger.com`

**Configuration:**
```bash
# .env.production (frontend)
NEXT_PUBLIC_API_URL=https://api.voice-ledger.com
NEXT_PUBLIC_API_KEY=your_production_api_key
```

---

## CORS Configuration (FastAPI)

**Update in `voice/service/api.py`:**

```python
from fastapi.middleware.cors import CORSMiddleware

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Development
        "https://dashboard.voice-ledger.com",  # Production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Security Considerations

1. **API Key Management:**
   - Use environment variables
   - Never commit API keys to Git
   - Rotate keys regularly

2. **HTTPS:**
   - Always use HTTPS in production
   - Enforce HTTPS redirects

3. **Authentication:**
   - Implement JWT tokens for user sessions
   - Add rate limiting to API endpoints

4. **Input Validation:**
   - Validate file types on frontend
   - Backend already validates (FastAPI)

---

## File Structure (Recommended)

```
voice-ledger-dashboard/
├── app/                      # Next.js 13+ App Router
│   ├── layout.tsx           # Root layout
│   ├── page.tsx             # Home page
│   ├── upload/
│   │   └── page.tsx         # Voice upload page
│   ├── batches/
│   │   ├── page.tsx         # Batch list
│   │   └── [id]/
│   │       └── page.tsx     # Batch details
│   ├── dpp/
│   │   └── [id]/
│   │       └── page.tsx     # DPP viewer
│   └── analytics/
│       └── page.tsx         # Analytics dashboard
├── components/              # Reusable components
│   ├── AudioUploader.tsx
│   ├── BatchTable.tsx
│   ├── TaskStatusDisplay.tsx
│   └── DPPViewer.tsx
├── lib/                     # Utilities
│   ├── api.ts              # API client functions
│   ├── types.ts            # TypeScript types
│   └── utils.ts            # Helper functions
├── public/                  # Static assets
│   └── logo.png
├── .env.local              # Environment variables
├── package.json
├── tsconfig.json
└── next.config.js
```

---

## Testing

### Unit Tests (Jest + React Testing Library)

```bash
npm install -D jest @testing-library/react @testing-library/jest-dom
```

```typescript
// __tests__/AudioUploader.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { AudioUploader } from '@/components/AudioUploader';

test('uploads audio file', async () => {
  render(<AudioUploader />);
  
  const file = new File(['audio'], 'test.wav', { type: 'audio/wav' });
  const input = screen.getByLabelText(/upload/i);
  
  fireEvent.change(input, { target: { files: [file] } });
  
  expect(screen.getByText(/test.wav/i)).toBeInTheDocument();
});
```

---

## Performance Optimization

1. **Code Splitting:**
   - Next.js automatically splits code by route
   - Use dynamic imports for heavy components

2. **Image Optimization:**
   - Use Next.js `<Image>` component
   - Lazy load images

3. **API Response Caching:**
   - Use SWR or React Query
   - Cache batch lists, DPPs

4. **Bundle Size:**
   - Analyze with `npm run build` and `@next/bundle-analyzer`
   - Tree-shake unused code

---

## Estimated Timeline

### Phase 1: Setup & Basic UI (2-3 days)
- [x] Create Next.js project
- [x] Setup API client
- [x] Build audio uploader component
- [x] Build batch list page
- [x] Basic styling

### Phase 2: Advanced Features (3-4 days)
- [x] Real-time status updates
- [x] DPP viewer
- [x] Batch details page
- [x] Search and filters
- [x] Pagination

### Phase 3: Analytics & Polish (2-3 days)
- [x] Analytics dashboard
- [x] Charts and graphs
- [x] Export functionality
- [x] Responsive design
- [x] Testing

### Phase 4: Deployment (1 day)
- [x] Configure production environment
- [x] Deploy to Vercel
- [x] Setup custom domain
- [x] Configure CORS
- [x] Performance testing

**Total: 8-11 days** for full-featured dashboard

---

## Alternative: Quick Python Dashboard (If Needed Fast)

If you need something **immediately** and JavaScript setup is too much:

### Streamlit (Quickest)

```bash
pip install streamlit
```

```python
# dashboard.py
import streamlit as st
import requests

st.title("Voice Ledger Dashboard")

uploaded_file = st.file_uploader("Upload Audio", type=['wav', 'mp3'])

if uploaded_file:
    files = {'audio': uploaded_file}
    response = requests.post(
        'http://localhost:8000/voice/upload-async',
        files=files,
        headers={'X-API-Key': 'your-api-key'}
    )
    task_id = response.json()['task_id']
    st.success(f"Uploaded! Task ID: {task_id}")
```

**Run:** `streamlit run dashboard.py`

**Pros:** 5 minutes to get started  
**Cons:** Not production-ready, limited customization

---

## Conclusion

**Recommendation:** Build the dashboard in **Next.js + TypeScript** for:
- Professional, production-ready UI
- Mobile responsiveness
- Real-time updates
- Easy deployment
- Scalability

**Your FastAPI backend stays unchanged** - it's already perfect for this architecture!

---

## References

- Next.js Documentation: https://nextjs.org/docs
- React Documentation: https://react.dev
- FastAPI CORS: https://fastapi.tiangolo.com/tutorial/cors/
- Vercel Deployment: https://vercel.com/docs
- Tailwind CSS: https://tailwindcss.com/docs

---

**Next Steps (When Ready):**
1. Create new Next.js project in separate folder
2. Copy API integration code from this guide
3. Build AudioUploader component
4. Test with existing FastAPI backend
5. Iterate and expand features

**No backend changes required!** 🚀
