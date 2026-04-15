export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-24">
      <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
        CampScout
      </h1>
      <p className="mt-4 max-w-md text-center text-lg text-muted-foreground">
        Find available campsites near you. Search by location and dates across
        Recreation.gov campgrounds.
      </p>
    </div>
  );
}
