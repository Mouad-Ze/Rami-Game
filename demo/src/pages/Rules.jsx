import "./Rules.css";
import { useNavigate } from "react-router-dom";

export default function Rules() {
  const navigate = useNavigate();

  return (
    <div className="rules-wrapper">
    <button
  onClick={() => navigate("/")}
  style={{
    position: "absolute",
    top: 20,
    right: 20,
    padding: "8px 14px",
    background: "rgba(255, 215, 0, 0.9)",
    border: "2px solid #543",
    color: "#111",
    borderRadius: 10,
    cursor: "pointer",
    fontWeight: "bold",
  }}
>
  Back to Game
</button>

      <div className="rules-card">
        <h1 className="rules-title">Rami — Official Rules</h1>

        <section>
          <h2>Objective</h2>
          <p>
            The goal is to arrange all 13 cards in your hand into valid
            combinations and declare victory. A winning hand must contain:
          </p>
          <ul>
            <li>At least <strong>one Free Tirsi</strong> (set with no joker)</li>
            <li>At least <strong>one Free Suivi</strong> (run with no joker)</li>
          </ul>
        </section>

        <section>
          <h2>Deck</h2>
          <p>
            Rami uses a <strong>108-card deck</strong>: two full 52-card decks
            plus 4 Jokers (2 red, 2 black). The Ace may be used low (A–2–3) or
            high (Q–K–A), but cannot wrap (K–A–2).
          </p>
        </section>

        <section>
          <h2>Gameplay</h2>
          <ul>
            <li>Players receive 13 cards.</li>
            <li>Turns proceed counter-clockwise.</li>
            <li>On your turn, you must first <strong>draw</strong> (deck or discard).</li>
            <li>You then <strong>discard</strong> one card.</li>
            <li>You may declare “I won” only after drawing but before discarding.</li>
          </ul>
        </section>

        <section>
          <h2>Valid Combinations</h2>

          <h3>Tirsi (Set)</h3>
          <p>A group of 3 or 4 cards of the same rank and all different suits.</p>
          <ul>
            <li>✔ 7♥, 7♣, 7♠</li>
            <li>❌ Suits may not repeat</li>
            <li>✔ May contain 1 Joker (max)</li>
          </ul>

          <h3>Suivi (Run)</h3>
          <p>
            A sequence of 3+ consecutive cards of the same suit
            (Ace low or Ace high allowed).
          </p>
          <ul>
            <li>✔ A♣–2♣–3♣</li>
            <li>✔ Q♦–K♦–A♦</li>
            <li>❌ K–A–2 is invalid (no wrap)</li>
            <li>✔ May contain 1 Joker (max)</li>
          </ul>
        </section>

        <section>
          <h2>Winning</h2>
          <p>
            To win, all 13 cards must be fully grouped into valid Tirsi or
            Suivi combinations. At least one of each must be <strong>free</strong>
            (contain no Joker). After declaring, you place your combinations
            on the table and discard your final card.
          </p>
        </section>
      </div>
    </div>
  );
}
