import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'screens/home_screen.dart';
import 'screens/games_screen.dart';
import 'screens/picks_screen.dart';
import 'screens/profile_screen.dart';

void main() {
  runApp(const ProviderScope(child: EdgeCrewApp()));
}

class EdgeCrewApp extends StatelessWidget {
  const EdgeCrewApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Edge Crew',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFFD4A017),
          secondary: Color(0xFF00D4AA),
          surface: Color(0xFF1A1A1A),
          background: Color(0xFF0A0A0F),
          error: Color(0xFFEF4444),
        ),
        scaffoldBackgroundColor: const Color(0xFF0A0A0F),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF1A1A1A),
          elevation: 0,
          centerTitle: true,
          titleTextStyle: TextStyle(
            color: Color(0xFFD4A017),
            fontSize: 20,
            fontWeight: FontWeight.bold,
          ),
        ),
        bottomNavigationBarTheme: const BottomNavigationBarThemeData(
          backgroundColor: Color(0xFF1A1A1A),
          selectedItemColor: Color(0xFFD4A017),
          unselectedItemColor: Colors.grey,
          type: BottomNavigationBarType.fixed,
        ),
        cardTheme: CardTheme(
          color: const Color(0xFF1A1A1A),
          elevation: 4,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      home: const MainNavigation(),
    );
  }
}

class MainNavigation extends StatefulWidget {
  const MainNavigation({super.key});

  @override
  State<MainNavigation> createState() => _MainNavigationState();
}

class _MainNavigationState extends State<MainNavigation> {
  int _selectedIndex = 0;

  final _screens = const [
    HomeScreen(),
    GamesScreen(),
    PicksScreen(),
    ProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _screens[_selectedIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: (index) => setState(() => _selectedIndex = index),
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.dashboard_outlined),
            activeIcon: Icon(Icons.dashboard),
            label: 'Home',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.sports_basketball_outlined),
            activeIcon: Icon(Icons.sports_basketball),
            label: 'Games',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.check_circle_outline),
            activeIcon: Icon(Icons.check_circle),
            label: 'Picks',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.person_outline),
            activeIcon: Icon(Icons.person),
            label: 'Profile',
          ),
        ],
      ),
    );
  }
}
