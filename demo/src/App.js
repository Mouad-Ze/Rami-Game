import "./App.css";
import { useState } from 'react';
import GameBoard   from './components/GameBoard';
import Rules from "./pages/Rules";
import { BrowserRouter as Router, Routes, Route, Link } from "react-router-dom";
export default function App() {
  const [playerName, setPlayerName] = useState(null);


  return(<Router>
    <Routes>
      <Route path="/" element={<GameBoard playerName={playerName} />} />
      <Route path="/rules" element={<Rules />} />
    </Routes>

  </Router> );
}