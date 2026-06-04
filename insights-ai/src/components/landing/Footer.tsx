import { Link } from 'react-router-dom'
import { Sparkles } from 'lucide-react'

const footerLinks = {
  Product: ['Features', 'How it works', 'Pricing', 'Changelog'],
  Company: ['About', 'Blog', 'Careers', 'Contact'],
  Legal: ['Privacy', 'Terms', 'Security', 'Status'],
}

export default function Footer() {
  return (
    <footer className="bg-[#0A0A0A] border-t border-[#2A2A2A] py-12 px-6">
      <div className="max-w-7xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-12">
          {/* Col 1 — Brand */}
          <div className="md:col-span-1">
            <Link to="/" className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg bg-purple-600/20 flex items-center justify-center border border-purple-500/30">
                <Sparkles className="w-3.5 h-3.5 text-purple-400" />
              </div>
              <span className="font-bold text-white text-base">
                Insights<span className="text-purple-400">.ai</span>
              </span>
            </Link>
            <p className="text-[#A1A1AA] text-sm leading-relaxed mb-6">
              Turn your data into decisions powered by ML.
            </p>
          </div>

          {/* Cols 2–4 — Links */}
          {Object.entries(footerLinks).map(([heading, links]) => (
            <div key={heading}>
              <h4 className="text-white font-semibold text-sm mb-4">{heading}</h4>
              <ul className="space-y-2.5">
                {links.map((link) => (
                  <li key={link}>
                    <a
                      href="#"
                      className="text-[#A1A1AA] hover:text-white text-sm transition-colors duration-200"
                    >
                      {link}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="border-t border-[#2A2A2A] pt-6 flex flex-col sm:flex-row items-center justify-between gap-2">
          <p className="text-[#52525B] text-sm">
            © 2025 Insights.ai. All rights reserved.
          </p>
          <p className="text-[#52525B] text-sm">
            Made with ♥ for data-curious humans
          </p>
        </div>
      </div>
    </footer>
  )
}
