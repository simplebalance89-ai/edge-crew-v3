import 'package:flutter/material.dart';

class PickCard extends StatelessWidget {
  final String game;
  final String pick;
  final String grade;
  final int confidence;
  final String status;
  final VoidCallback? onTap;

  const PickCard({
    super.key,
    required this.game,
    required this.pick,
    required this.grade,
    required this.confidence,
    required this.status,
    this.onTap,
  });

  Color get _gradeColor {
    if (grade.startsWith('A')) return const Color(0xFF10B981);
    if (grade.startsWith('B')) return const Color(0xFF38BDF8);
    if (grade.startsWith('C')) return const Color(0xFFF59E0B);
    return const Color(0xFFEF4444);
  }

  Color get _statusColor {
    switch (status) {
      case 'LOCK':
        return const Color(0xFF10B981);
      case 'ALIGNED':
        return const Color(0xFF38BDF8);
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
          child: Row(
            children: [
              // Grade Circle
              Container(
                width: 60,
                height: 60,
                decoration: BoxDecoration(
                  color: _gradeColor.withOpacity(0.2),
                  border: Border.all(color: _gradeColor, width: 2),
                  shape: BoxShape.circle,
                ),
                child: Center(
                  child: Text(
                    grade,
                    style: TextStyle(
                      color: _gradeColor,
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 16),
              
              // Content
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      game,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      pick,
                      style: TextStyle(
                        fontSize: 14,
                        color: Colors.grey[400],
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: _statusColor.withOpacity(0.2),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            status,
                            style: TextStyle(
                              color: _statusColor,
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          '$confidence% confidence',
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey[500],
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              
              // Arrow
              const Icon(Icons.chevron_right, color: Colors.grey),
            ],
          ),
        ),
      ),
    );
  }
}
