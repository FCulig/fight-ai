// react-router-dom with BrowserRouter swapped for a MemoryRouter that opens at
// the screen's route, so the real App renders whichever URL the design page
// is served from.
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom-real';
export * from 'react-router-dom-real';

export function BrowserRouter({ children }: { children?: ReactNode }) {
  const path = (window as unknown as { __SCREEN: { path: string } }).__SCREEN.path;
  return <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>;
}
