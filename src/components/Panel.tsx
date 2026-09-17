import React from 'react';

export const buttonClass = 'px-4 py-2 rounded-lg bg-cyan-700 text-white disabled:opacity-40 hover:bg-cyan-600 text-sm';
export const inputClass = 'w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-sm text-slate-100';
export function Panel({ title, children }: React.PropsWithChildren<{title: string}>) {
  return <section className="flex-1 overflow-auto p-6 space-y-5"><h1 className="text-xl font-bold">{title}</h1>{children}</section>;
}
