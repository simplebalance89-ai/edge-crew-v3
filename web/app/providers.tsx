'use client';

import { ReactNode } from 'react';
import { SWRConfig } from 'swr';

export function Providers({ children }: { children: ReactNode }) {
  return (
    <SWRConfig
      value={{
        refreshInterval: 30000,
        revalidateOnFocus: true,
        errorRetryCount: 3,
        provider: () => new Map(),
      }}
    >
      {children}
    </SWRConfig>
  );
}
