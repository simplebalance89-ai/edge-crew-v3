# Edge Crew v3.0 Frontend

A modern Next.js 14 frontend for Edge Crew sports analytics platform with real-time updates.

## Features

- **Real-time Updates**: Server-Sent Events (SSE) for live grade updates
- **Two-Lane Analysis**: Side-by-side OUR PROCESS vs AI PROCESS visualization
- **Dark Theme**: Premium dark UI with gold (#D4A017) accents
- **Mobile-Responsive**: Works on all devices
- **PWA Support**: Installable as a progressive web app

## Tech Stack

- Next.js 14 (App Router)
- React 18
- TypeScript
- Tailwind CSS
- SWR (data fetching)
- Recharts (visualizations)
- Lucide React (icons)

## Getting Started

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

## Project Structure

```
app/
  ├── layout.tsx       # Root layout with providers
  ├── page.tsx         # Main dashboard
  ├── peter/           # Pro Edge interface
  │   └── page.tsx
  └── globals.css      # Global styles

components/
  ├── TwoLaneDisplay.tsx    # OUR vs AI comparison
  ├── GameCard.tsx          # Game display card
  ├── ConvergenceBadge.tsx  # Status badges
  ├── ConfidenceMeter.tsx   # Visual confidence
  └── LineMovementChart.tsx # Line history

hooks/
  ├── useRealtime.ts   # SSE hook
  └── useGrades.ts     # SWR data hooks

lib/
  ├── api.ts           # API client
  ├── types.ts         # TypeScript types
  └── utils.ts         # Utilities
```

## Environment Variables

Copy `.env.example` to `.env.local` and configure:

- `NEXT_PUBLIC_API_URL` - Backend API URL

## Docker

```bash
# Build image
docker build -t edge-crew-v3 .

# Run container
docker run -p 3000:3000 edge-crew-v3
```

## License

Private - Edge Crew
