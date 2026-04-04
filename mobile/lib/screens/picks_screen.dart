import 'package:flutter/material.dart';
import '../widgets/pick_card.dart';

class PicksScreen extends StatelessWidget {
  const PicksScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('MY PICKS'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Stats Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  const Row(
                    mainAxisAlignment: MainAxisAlignment.spaceAround,
                    children: [
                      _StatBox(label: 'WINS', value: '24', color: Colors.green),
                      _StatBox(label: 'LOSSES', value: '12', color: Colors.red),
                      _StatBox(label: 'ROI', value: '+18%', color: Colors.amber),
                    ],
                  ),
                  const SizedBox(height: 16),
                  LinearProgressIndicator(
                    value: 24 / 36,
                    backgroundColor: Colors.grey[800],
                    valueColor: const AlwaysStoppedAnimation(Color(0xFFD4A017)),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '67% Win Rate',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey[500],
                    ),
                  ),
                ],
              ),
            ),
          ),
          
          const SizedBox(height: 20),
          
          // Active Picks
          const Text(
            'ACTIVE PICKS',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              letterSpacing: 1,
            ),
          ),
          const SizedBox(height: 12),
          
          PickCard(
            game: 'Lakers vs Warriors',
            pick: 'Lakers -4.5',
            grade: 'A',
            confidence: 85,
            status: 'LOCK',
            onTap: () {},
          ),
          const SizedBox(height: 12),
          PickCard(
            game: 'Celtics vs Heat',
            pick: 'Over 215.5',
            grade: 'A-',
            confidence: 78,
            status: 'ALIGNED',
            onTap: () {},
          ),
          
          const SizedBox(height: 20),
          
          // History
          const Text(
            'RECENT HISTORY',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              letterSpacing: 1,
            ),
          ),
          const SizedBox(height: 12),
          
          _HistoryItem(
            game: 'Nuggets vs Suns',
            pick: 'Nuggets -3',
            result: 'WIN',
            profit: '+1.5u',
            date: 'Apr 3',
          ),
          _HistoryItem(
            game: 'Thunder vs Mavs',
            pick: 'Under 228',
            result: 'WIN',
            profit: '+1u',
            date: 'Apr 3',
          ),
          _HistoryItem(
            game: 'Sixers vs Heat',
            pick: 'Sixers ML',
            result: 'LOSS',
            profit: '-1u',
            date: 'Apr 2',
          ),
        ],
      ),
    );
  }
}

class _StatBox extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _StatBox({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: 28,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        Text(
          label,
          style: TextStyle(
            fontSize: 10,
            color: Colors.grey[500],
            letterSpacing: 1,
          ),
        ),
      ],
    );
  }
}

class _HistoryItem extends StatelessWidget {
  final String game;
  final String pick;
  final String result;
  final String profit;
  final String date;

  const _HistoryItem({
    required this.game,
    required this.pick,
    required this.result,
    required this.profit,
    required this.date,
  });

  @override
  Widget build(BuildContext context) {
    final isWin = result == 'WIN';
    
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        title: Text(game),
        subtitle: Text(pick),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: isWin ? Colors.green.withOpacity(0.2) : Colors.red.withOpacity(0.2),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                result,
                style: TextStyle(
                  color: isWin ? Colors.green : Colors.red,
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            const SizedBox(height: 4),
            Text(
              profit,
              style: TextStyle(
                color: isWin ? Colors.green : Colors.red,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
