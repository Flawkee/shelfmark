import type { ReactNode } from 'react';
import { createContext, useContext, useMemo } from 'react';

interface LibraryAvailabilityContextValue {
  libraryUrl: string;
  audiobookLibraryUrl: string;
  allowMissingType: boolean;
}

const LibraryAvailabilityContext = createContext<LibraryAvailabilityContextValue>({
  libraryUrl: '',
  audiobookLibraryUrl: '',
  allowMissingType: true,
});

export function useLibraryAvailability(): LibraryAvailabilityContextValue {
  return useContext(LibraryAvailabilityContext);
}

interface LibraryAvailabilityProviderProps {
  libraryUrl: string;
  audiobookLibraryUrl: string;
  allowMissingType: boolean;
  children: ReactNode;
}

export function LibraryAvailabilityProvider({
  libraryUrl,
  audiobookLibraryUrl,
  allowMissingType,
  children,
}: LibraryAvailabilityProviderProps) {
  const value = useMemo(
    () => ({ libraryUrl, audiobookLibraryUrl, allowMissingType }),
    [libraryUrl, audiobookLibraryUrl, allowMissingType],
  );

  return (
    <LibraryAvailabilityContext.Provider value={value}>
      {children}
    </LibraryAvailabilityContext.Provider>
  );
}
