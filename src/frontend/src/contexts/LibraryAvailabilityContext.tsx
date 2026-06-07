import type { ReactNode } from 'react';
import { createContext, useContext, useMemo } from 'react';

import type { ContentType } from '../types';

interface LibraryAvailabilityContextValue {
  libraryUrl: string;
  audiobookLibraryUrl: string;
  allowMissingType: boolean;
  searchContentType: ContentType;
  combinedMode: boolean;
}

const LibraryAvailabilityContext = createContext<LibraryAvailabilityContextValue>({
  libraryUrl: '',
  audiobookLibraryUrl: '',
  allowMissingType: true,
  searchContentType: 'ebook',
  combinedMode: false,
});

export function useLibraryAvailability(): LibraryAvailabilityContextValue {
  return useContext(LibraryAvailabilityContext);
}

interface LibraryAvailabilityProviderProps {
  libraryUrl: string;
  audiobookLibraryUrl: string;
  allowMissingType: boolean;
  searchContentType: ContentType;
  combinedMode: boolean;
  children: ReactNode;
}

export function LibraryAvailabilityProvider({
  libraryUrl,
  audiobookLibraryUrl,
  allowMissingType,
  searchContentType,
  combinedMode,
  children,
}: LibraryAvailabilityProviderProps) {
  const value = useMemo(
    () => ({ libraryUrl, audiobookLibraryUrl, allowMissingType, searchContentType, combinedMode }),
    [libraryUrl, audiobookLibraryUrl, allowMissingType, searchContentType, combinedMode],
  );

  return (
    <LibraryAvailabilityContext.Provider value={value}>
      {children}
    </LibraryAvailabilityContext.Provider>
  );
}
