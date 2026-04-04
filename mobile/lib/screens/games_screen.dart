import 'package:flutter/material.dart';
import '../widgets/game_card.dart';

class GamesScreen extends StatefulWidget {
  const GamesScreen({super.key});

  @override
  State<GamesScreen> createState() => _GamesScreenState();
}

class _GamesScreenState extends State<GamesScreen> {
  String _selectedSport = 'NBA';
  final List<String> _sports = ['NBA', 'NHL', 'MLB', 'NFL', 'NCAAB', 'Soccer'];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('GAMES'),
      ),
      body: Column(
        children: [
          // Sport Selector
          Container(
            height: 50,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              itemCount: _sports.length,
              itemBuilder: (context, index) {
                final sport = _sports[index];
                final isSelected = sport == _selectedSport;
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text(sport),
                    selected: isSelected,
                    onSelected: (selected) {
                      if (selected) {
                        setState(() => _selectedSport = sport);
                      }
                    },
                    backgroundColor: Colors.grey[800],
                    selectedColor: const Color(0xFFD4A017),
                    labelStyle: TextStyle(
                      color: isSelected ? Colors.black : Colors.white,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                );
              },
            ),
          ),
          
          // Games List
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: 3,
              itemBuilder: (context, index) {
                final games = [
                  ('Lakers', 'Warriors', '7:30 PM', 'A', 'A-', 'LOCK'),
                  ('Celtics', 'Heat', '8:00 PM', 'B+', 'B+', 'ALIGNED'),
                  ('Nuggets', 'Suns', '9:00 PM', 'A-', 'C+', 'DIVERGENT'),
                ];
                
                final game = games[index];
                return GameCard(
                  homeTeam: game.$1,
                  awayTeam: game.$2,
                  time: game.$3,
                  ourGrade: game.$4,
                  aiGrade: game.$5,
                  status: game.$6,
                  onTap: () {},
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
