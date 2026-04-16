import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-24">
      <div className="max-w-lg text-center">
        <h1 className="font-heading text-5xl font-bold tracking-tight text-primary sm:text-6xl">
          CampScout
        </h1>
        <p className="mt-6 text-lg leading-relaxed text-muted-foreground">
          Find your perfect campsite in the wild. Search across Recreation.gov and
          California state parks by location and dates, set alerts for sold-out
          campgrounds, and never miss an opening again.
        </p>
        <Link href="/search">
          <button className="mt-8 rounded-lg bg-primary px-8 py-3 text-base font-semibold text-primary-foreground transition-colors hover:bg-primary/90">
            Start searching
          </button>
        </Link>
      </div>
    </div>
  );
}
