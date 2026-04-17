import Image from "next/image";
import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col">
      {/* Hero with background image */}
      <section className="relative flex flex-col items-center justify-center px-4 py-32 sm:py-40">
        <Image
          src="/hero-bg.jpg"
          alt="Mountain landscape"
          fill
          className="object-cover"
          priority
        />
        {/* Dark overlay for text readability */}
        <div className="absolute inset-0 bg-black/45" />
        <div className="relative z-10 max-w-lg text-center">
          <h1 className="font-heading text-5xl font-bold tracking-tight text-white drop-shadow-lg sm:text-6xl">
            CampScout
          </h1>
          <p className="mt-6 text-lg leading-relaxed text-white/90 drop-shadow">
            Find your perfect campsite in the wild. Search across Recreation.gov
            and California state parks by location and dates, set alerts for
            sold-out campgrounds, and never miss an opening again.
          </p>
          <Link href="/search">
            <button className="mt-8 cursor-pointer rounded-lg bg-primary px-8 py-3 text-base font-semibold text-primary-foreground transition-colors hover:bg-primary/90 shadow-lg">
              Start searching
            </button>
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="border-t border-border bg-card px-4 py-20">
        <div className="mx-auto max-w-4xl">
          <h2 className="font-heading text-center text-3xl font-bold text-primary">
            How it works
          </h2>
          <div className="mt-12 grid gap-8 sm:grid-cols-3">
            <div className="text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-2xl">
                🔍
              </div>
              <h3 className="mt-4 font-heading text-lg font-semibold">
                Search by location
              </h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Pick a spot on the map and set your radius. We search 890+
                campgrounds across Recreation.gov and California state parks.
              </p>
            </div>
            <div className="text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-2xl">
                🔔
              </div>
              <h3 className="mt-4 font-heading text-lg font-semibold">
                Set alerts for sold-out sites
              </h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Found a campground that&apos;s booked? Set an alert and
                we&apos;ll email you the moment a cancellation opens up.
              </p>
            </div>
            <div className="text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-2xl">
                ⛺
              </div>
              <h3 className="mt-4 font-heading text-lg font-semibold">
                Book instantly
              </h3>
              <p className="mt-2 text-sm text-muted-foreground">
                One click takes you straight to the booking page. No middleman,
                no markup — just you and the campsite.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Photo gallery + CTA */}
      <section className="px-4 py-20">
        <div className="mx-auto max-w-5xl">
          <h2 className="font-heading text-center text-3xl font-bold text-primary">
            Book your next adventure today
          </h2>
          <div className="mt-10 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="overflow-hidden rounded-lg">
              <Image
                src="/hero-1.jpg"
                alt="Lake sunset"
                width={400}
                height={300}
                className="h-48 w-full object-cover transition-transform hover:scale-105 sm:h-56"
              />
            </div>
            <div className="overflow-hidden rounded-lg">
              <Image
                src="/hero-2.jpg"
                alt="Oak tree hills"
                width={400}
                height={300}
                className="h-48 w-full object-cover transition-transform hover:scale-105 sm:h-56"
              />
            </div>
            <div className="overflow-hidden rounded-lg">
              <Image
                src="/hero-3.jpg"
                alt="Snowy mountain"
                width={400}
                height={300}
                className="h-48 w-full object-cover transition-transform hover:scale-105 sm:h-56"
              />
            </div>
            <div className="overflow-hidden rounded-lg">
              <Image
                src="/hero-4.jpg"
                alt="Lakeside pines"
                width={400}
                height={300}
                className="h-48 w-full object-cover transition-transform hover:scale-105 sm:h-56"
              />
            </div>
          </div>
          <div className="mt-10 text-center">
            <Link href="/search">
              <button className="cursor-pointer rounded-lg bg-primary px-8 py-3 text-base font-semibold text-primary-foreground transition-colors hover:bg-primary/90">
                Find your campsite
              </button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
