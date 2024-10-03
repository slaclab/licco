"use client";

import { Alignment, AnchorButton, Navbar, Tooltip } from '@blueprintjs/core';
import { usePathname } from 'next/navigation';
import { Anchor } from 'react-bootstrap';
import styles from './navbar.module.css';

const links = [
    { link: '/', label: 'Projects' },
    { link: '/ffts', label: 'FFTs' },
];


export function Navigation() {
    const path = usePathname();
    const btnStyle = (path: string, link: string) => {
        if (path == link) {
            return `${styles.btn} ${styles.btnActive} bp5-minimal`;
        }
        return `${styles.btn} bp5-minimal`;
    }

    return (
        <Navbar className={styles.navbar}>
            <Navbar.Group align={Alignment.LEFT}>
                <Navbar.Heading>
                    <Anchor href="/" style={{ fontSize: "1.3rem", textDecoration: "none", fontWeight: "bold" }}>
                        {/* <img className={styles.logo} src="/assets/licco-logo.png" alt="Licco logo" /> */}
                        Machine Configuration Database
                    </Anchor>
                </Navbar.Heading>
            </Navbar.Group>
            <Navbar.Group align={Alignment.LEFT}>
                {links.map((l, i) => {
                    return <AnchorButton key={i} href={l.link} active={path == l.link} className={`${btnStyle(path, l.link)}`}>{l.label}</AnchorButton>
                })}
            </Navbar.Group>
            <Navbar.Group align={Alignment.RIGHT}>
                <Tooltip content="Machine Configuration Database Help (on Confluence)" position="bottom">
                    <AnchorButton className={`${styles.btn} bp5-minimal`} href="https://confluence.slac.stanford.edu/display/PCDS/Machine+Configuration+Database+Guide">?</AnchorButton>
                </Tooltip>
            </Navbar.Group>
        </Navbar>
    );
}