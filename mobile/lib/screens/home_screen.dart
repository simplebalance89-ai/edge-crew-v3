import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../widgets/convergence_card.dart';
import '../widgets/pick_card.dart';
import '../widgets/stats_summary.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('EDGE CREW'),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () {},
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          // Refresh data
          await Future.delayed(const Duration(seconds: 1));
        },
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Stats Summary
            const StatsSummary(),
            const SizedBox(height: 20),
            
            // Today's Picks Section
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  "TODAY'S PICKS",
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1,
                  ),
                ),
                TextButton(
                  onPressed: () {},
                  child: const Text('See All'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            
            // Pick Cards
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
            
            // Live Convergence Section
            const Text(
              'LIVE CONVERGENCE',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                letterSpacing: 1,
              ),
            ),
            const SizedBox(height: 12),
            
            // Convergence Cards
            ConvergenceCard(
              game: 'Nuggets vs Suns',
              ourGrade: 7.8,
              aiGrade: 7.5,
              consensus: 7.7,
              status: 'ALIGNED',
              delta: 0.3,
              isLive: true,
              onTap: () {},
            ),
            const SizedBox(height: 12),
            ConvergenceCard(
              game: 'Thunder vs Mavericks',
              ourGrade: 6.2,
              aiGrade: 8.1,
              consensus: 7.0,
              status: 'DIVERGENT',
              delta: 1.9,
              isLive: true,
              onTap: () {},
            ),
          ],
        ),
      ),
    );
  }
}
