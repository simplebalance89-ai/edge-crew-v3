import 'package:flutter/material.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('PROFILE'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Profile Header
          Center(
            child: Column(
              children: [
                CircleAvatar(
                  radius: 50,
                  backgroundColor: const Color(0xFFD4A017),
                  child: const Text(
                    'P',
                    style: TextStyle(
                      fontSize: 40,
                      fontWeight: FontWeight.bold,
                      color: Colors.black,
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                const Text(
                  'Peter',
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'The Director',
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.grey[500],
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    _Badge(label: 'PRO', color: Color(0xFFD4A017)),
                    SizedBox(width: 8),
                    _Badge(label: '24-12', color: Colors.green),
                  ],
                ),
              ],
            ),
          ),
          
          const SizedBox(height: 32),
          
          // Settings
          const Text(
            'SETTINGS',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              letterSpacing: 1,
            ),
          ),
          const SizedBox(height: 12),
          
          _SettingTile(
            icon: Icons.notifications,
            title: 'Notifications',
            subtitle: 'Get alerts for high-confidence picks',
            onTap: () {},
          ),
          _SettingTile(
            icon: Icons.sports_basketball,
            title: 'Favorite Sports',
            subtitle: 'NBA, NHL, MLB',
            onTap: () {},
          ),
          _SettingTile(
            icon: Icons.account_balance_wallet,
            title: 'Bankroll',
            subtitle: 'Starting: $1000 | Current: $1247',
            onTap: () {},
          ),
          _SettingTile(
            icon: Icons.security,
            title: 'Security',
            subtitle: 'Biometric login enabled',
            onTap: () {},
          ),
          
          const SizedBox(height: 32),
          
          // App Info
          const Text(
            'ABOUT',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              letterSpacing: 1,
            ),
          ),
          const SizedBox(height: 12),
          
          _SettingTile(
            icon: Icons.info,
            title: 'Version',
            subtitle: '3.0.0 (Build 2026.04.04)',
            onTap: null,
          ),
          _SettingTile(
            icon: Icons.help,
            title: 'Help & Support',
            subtitle: 'Documentation, FAQ, Contact',
            onTap: () {},
          ),
          
          const SizedBox(height: 32),
          
          // Logout
          ElevatedButton(
            onPressed: () {},
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red.withOpacity(0.2),
              foregroundColor: Colors.red,
              padding: const EdgeInsets.symmetric(vertical: 16),
            ),
            child: const Text('LOG OUT'),
          ),
        ],
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  final String label;
  final Color color;

  const _Badge({required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.2),
        border: Border.all(color: color),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }
}

class _SettingTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback? onTap;

  const _SettingTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Icon(icon, color: const Color(0xFFD4A017)),
        title: Text(title),
        subtitle: Text(subtitle),
        trailing: onTap != null 
            ? const Icon(Icons.chevron_right, color: Colors.grey)
            : null,
        onTap: onTap,
      ),
    );
  }
}
