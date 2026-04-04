import 'package:flutter/material.dart';

class ConvergenceCard extends StatelessWidget {
  final String game;
  final double ourGrade;
  final double aiGrade;
  final double consensus;
  final String status;
  final double delta;
  final bool isLive;
  final VoidCallback onTap;

  const ConvergenceCard({
    super.key,
    required this.game,
    required this.ourGrade,
    required this.aiGrade,
    required this.consensus,
    required this.status,
    required this.delta,
    this.isLive = false,
    required this.onTap,
  });

  Color get _statusColor {
    switch (status) {
      case 'LOCK':
        return const Color(0xFF10B981);
      case 'ALIGNED':
        return const Color(0xFF38BDF8);
      case 'DIVERGENT':
        return const Color(0xFFF59E0B);
      case 'CONFLICT':
        return const Color(0xFFEF4444);
      default:
        return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Text(
                      game,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  if (isLive)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.red,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: const Text(
                        'LIVE',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 16),
              
              // Two Lane Display
              Row(
                children: [
                  Expanded(
                    child: _buildLane(
                      'OUR PROCESS',
                      const Color(0xFFF72585),
                      ourGrade,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildLane(
                      'AI PROCESS',
                      const Color(0xFF00D4AA),
                      aiGrade,
                    ),
                  ),
                ],
              ),
              
              const SizedBox(height: 16),
              
              // Convergence Badge
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(
                  color: _statusColor.withOpacity(0.1),
                  border: Border.all(color: _statusColor),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Column(
                  children: [
                    Text(
                      status,
                      style: TextStyle(
                        color: _statusColor,
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 2,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Consensus: ${consensus.toStringAsFixed(1)} | Delta: ${delta.toStringAsFixed(1)}',
                      style: TextStyle(
                        color: _statusColor.withOpacity(0.8),
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLane(String title, Color color, double score) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        border: Border.all(color: color.withOpacity(0.3)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        children: [
          Text(
            title,
            style: TextStyle(
              color: color,
              fontSize: 10,
              fontWeight: FontWeight.bold,
              letterSpacing: 1,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            score.toStringAsFixed(1),
            style: TextStyle(
              color: color,
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}
