import { Link } from 'react-router-dom'
import Bulldog from '../components/Bulldog'
import { useShop } from '../shop'

const VALUES = [
  {
    title: 'Pride comes in many shades of blue',
    text: "Being part of Yale can mean a residential college, a varsity team, a graduate school, or a kid who just moved into a dorm. We stock gear for all of it, so nobody has to settle for a generic logo.",
  },
  {
    title: 'Comfort you can wear for years',
    text: 'We look for pieces that survive a New Haven winter, a hundred laundry cycles and a few reunions. If we wouldn\'t live in it ourselves, it doesn\'t make the shelf.',
  },
  {
    title: 'Honest shopping, online and off',
    text: "The price you see is the price you pay, and stock is shown live. Handsome Dan, our shop bulldog in the chat, looks up both before answering, so you won't be told something's in your size when it isn't.",
  },
  {
    title: 'Everyone gets a jersey',
    text: 'First-years, fifth-years, alumni, parents, grandparents, little siblings and lifelong fans. If you cheer for the Bulldogs, you belong here.',
  },
]

export default function About() {
  const { setChatOpen } = useShop()

  return (
    <div className="page about">
      <section className="about-hero">
        <p className="eyebrow">About Campus Customs</p>
        <h1>
          We make the clothes that make Yale feel like <em>home</em>.
        </h1>
        <p className="lede">
          Campus Customs is a New Haven shop on Broadway, a short walk from campus. We make and sell everyday Yale apparel
          for the people who keep Bulldog spirit going — on move-in day, at the Game, at Commencement and every ordinary
          Tuesday in between.
        </p>
      </section>

      <section className="about-story">
        <div>
          <h2>Our story</h2>
          <p>
            The idea is simple. A great sweatshirt is never just a sweatshirt. It's the hoodie you wore through finals, the
            crewneck your dad wears to every reunion, the tee you grab when the hockey team makes a run. We want Campus
            Customs to be where people find that piece.
          </p>
          <p>
            So we build our range around how people actually belong to Yale. That means designs for every residential
            college, for teams from fencing to field hockey, for the graduate and professional schools, and for the whole
            family — Mom, Dad, Grandpa, Aunt, Uncle and Cousin included.
          </p>
          <p>
            Lately we've added a new member of staff: <strong>Handsome Dan</strong>, our shop bulldog, who lives in the chat
            on every page (named in honour of Yale's famous mascot). Tell him who you're shopping for and he fetches pieces
            from our catalogue, puts them right on the page, and checks the live price and stock first.
          </p>
        </div>
        <aside className="visit-card">
          <h3>Come say hi</h3>
          <p className="visit-address">
            57 Broadway
            <br />
            New Haven, CT 06511
          </p>
          <p>
            Try things on in person, or browse online any time and save what you love to your account. Can't decide?
            Handsome Dan is always on duty.
          </p>
          <button className="btn btn-primary" onClick={() => setChatOpen(true)}>
            <Bulldog size={22} /> Chat with Handsome Dan
          </button>
        </aside>
      </section>

      <section aria-label="What we believe">
        <div className="section-head">
          <h2>What we believe</h2>
        </div>
        <div className="values">
          {VALUES.map((v) => (
            <div key={v.title} className="value">
              <span className="value-flower" aria-hidden>
                ✿
              </span>
              <h3>{v.title}</h3>
              <p>{v.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="cta-band">
        <div>
          <h2>Ready to find your piece?</h2>
          <p>Browse by college, team, school or family — or start with what's new.</p>
        </div>
        <Link to="/products" className="btn btn-primary">
          Shop the collection
        </Link>
      </section>
    </div>
  )
}
