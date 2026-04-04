import 'package:flutter/material.dart';

class GameCard extends StatelessWidget {
  final String homeTeam;
  final String awayTeam;
  final String time;
  final String ourGrade;
  final String aiGrade;
  final String status;
  final VoidCallback onTap;

  const GameCard({
    super.key,
    required this.homeTeam,
    required this.awayTeam,
    required this.time,
    required this.ourGrade,
    required this.aiGrade,
    required this.status,
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
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              // Teams
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          awayTeam,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          homeTeam,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Text(
                    time,
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey[500],
                    ),
                  ),
                ],
              ),
              
              const Divider(height: 24),
              
              // Grades
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  _buildGradeColumn('OUR', ourGrade, const Color(0xFFF72585)),
                  _buildStatusIndicator(),
                  _buildGradeColumn('AI', aiGrade, const Color(0xFF00D4AA)),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildGradeColumn(String label, String grade, Color color) {
    return Column(
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: 10,
            color: color,
            fontWeight: FontWeight.bold,
            letterSpacing: 1,
          ),
        ),
        const SizedBox(height: 4),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: color.withOpacity(0.2),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(
            grade,
            style: TextStyle(
              color: color,
              fontSize: 16,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildStatusIndicator() {
    return Column(
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: _statusColor,
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: _statusColor.withOpacity(0.5),
                blurRadius: 8,
                spreadRadius: 2,
              ),
            ],
          ),
        ),
        const SizedBox(height: 4),
        Text(
          status,
          style: TextStyle(
            fontSize: 10,
            color: _statusColor,
            fontWeight: FontWeight.bold,
          ),
        ),
      ],
    );
  }
}
